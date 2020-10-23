"""Main script for document matching in dual encoder style with AAN dataset."""
import functools
import itertools
import os
import time

from absl import app
from absl import flags
from absl import logging
from flax import jax_utils
from flax import nn
from flax import optim
from flax.metrics import tensorboard
from flax.training import checkpoints
from flax.training import common_utils
import jax
from jax import random
import jax.nn
import jax.numpy as jnp
from lra_benchmarks.matching import input_pipeline
from lra_benchmarks.models.transformer import transformer
from lra_benchmarks.utils import train_utils
from ml_collections import config_flags
import tensorflow.compat.v2 as tf

FLAGS = flags.FLAGS

config_flags.DEFINE_config_file(
    'config', None, 'Training configuration.', lock_config=True)
flags.DEFINE_string(
    'model_dir', default=None, help='Directory to store model data.')
flags.DEFINE_string(
    'task_name', default='aan', help='Directory to store model data.')
flags.DEFINE_string(
    'data_dir', default=None, help='Directory containing datasets.')


@functools.partial(jax.jit, static_argnums=(1, 2, 3, 4))
def create_model(key, flax_module, input1_shape, input2_shape, model_kwargs):
  module = flax_module.partial(**model_kwargs)
  with nn.stochastic(key):
    _, initial_params = module.init_by_shape(key, [(input1_shape, jnp.float32),
                                                   (input2_shape, jnp.float32)])
    model = nn.Model(module, initial_params)
  return model


def create_optimizer(model, learning_rate, weight_decay):
  optimizer_def = optim.Adam(
      learning_rate, beta1=0.9, beta2=0.98, eps=1e-9, weight_decay=weight_decay)
  optimizer = optimizer_def.create(model)
  return optimizer


def compute_metrics(logits, labels, weights):
  """Compute summary metrics."""
  loss, weight_sum = train_utils.compute_weighted_cross_entropy(
      logits, labels, num_classes=2, weights=None)
  acc, _ = train_utils.compute_weighted_accuracy(logits, labels, weights)
  metrics = {
      'loss': loss,
      'accuracy': acc,
      'denominator': weight_sum,
  }
  metrics = jax.lax.psum(metrics, 'batch')
  return metrics


def train_step(optimizer, batch, learning_rate_fn, dropout_rng=None):
  """Perform a single training step."""
  train_keys = ['inputs1', 'inputs2', 'targets']
  (inputs1, inputs2, targets) = [batch.get(k, None) for k in train_keys]

  # We handle PRNG splitting inside the top pmap, rather
  # than handling it outside in the training loop - doing the
  # latter can add some stalls to the devices.
  dropout_rng, new_dropout_rng = random.split(dropout_rng)

  def loss_fn(model):
    """Loss function used for training."""
    with nn.stochastic(dropout_rng):
      logits = model(inputs1, inputs2, train=True)
    loss, weight_sum = train_utils.compute_weighted_cross_entropy(
        logits, targets, num_classes=2, weights=None)
    mean_loss = loss / weight_sum
    return mean_loss, logits

  step = optimizer.state.step
  lr = learning_rate_fn(step)
  grad_fn = jax.value_and_grad(loss_fn, has_aux=True)
  (_, logits), grad = grad_fn(optimizer.target)
  grad = jax.lax.pmean(grad, 'batch')
  new_optimizer = optimizer.apply_gradient(grad, learning_rate=lr)
  metrics = compute_metrics(logits, targets, None)
  metrics['learning_rate'] = lr

  return new_optimizer, metrics, new_dropout_rng


def eval_step(model, batch):
  eval_keys = ['inputs1', 'inputs2', 'targets']
  (inputs1, inputs2, targets) = [batch.get(k, None) for k in eval_keys]
  logits = model(inputs1, inputs2, train=False)
  return compute_metrics(logits, targets, None)


def main(argv):
  if len(argv) > 1:
    raise app.UsageError('Too many command-line arguments.')

  tf.enable_v2_behavior()

  config = FLAGS.config
  logging.info('===========Config Dict============')
  logging.info(config)
  batch_size = config.batch_size
  learning_rate = config.learning_rate
  num_train_steps = config.num_train_steps
  num_eval_steps = config.num_eval_steps
  eval_freq = config.eval_frequency
  random_seed = config.random_seed
  model_type = config.model_type

  max_length = config.max_length

  if jax.host_id() == 0:
    summary_writer = tensorboard.SummaryWriter(
        os.path.join(FLAGS.model_dir, 'summary'))

  if batch_size % jax.device_count() > 0:
    raise ValueError('Batch size must be divisible by the number of devices')

  train_ds, eval_ds, test_ds, encoder = input_pipeline.get_matching_datasets(
      n_devices=jax.local_device_count(),
      task_name=FLAGS.task_name,
      data_dir=FLAGS.data_dir,
      batch_size=batch_size,
      fixed_vocab=None,
      max_length=max_length,
      tokenizer=config.tokenizer)

  vocab_size = encoder.vocab_size
  logging.info('Vocab Size: %d', vocab_size)

  train_ds = train_ds.repeat()

  train_iter = iter(train_ds)
  input_shape = (batch_size, max_length)

  model_kwargs = {
      'vocab_size': vocab_size,
      'emb_dim': config.emb_dim,
      'num_heads': config.num_heads,
      'num_layers': config.num_layers,
      'qkv_dim': config.qkv_dim,
      'mlp_dim': config.mlp_dim,
      'max_len': max_length,
      'classifier': True,
      'num_classes': 2,
      'classifier_pool': config.pooling_mode
  }

  rng = random.PRNGKey(random_seed)
  rng = jax.random.fold_in(rng, jax.host_id())
  rng, init_rng = random.split(rng)
  # We init the first set of dropout PRNG keys, but update it afterwards inside
  # the main pmap'd training update for performance.
  dropout_rngs = random.split(rng, jax.local_device_count())

  if model_type == 'transformer':
    model = create_model(init_rng, transformer.TransformerDualEncoder,
                         input_shape, input_shape, model_kwargs)
  else:
    raise ValueError('Model type not supported.')

  optimizer = create_optimizer(
      model, learning_rate, weight_decay=FLAGS.config.weight_decay)
  del model  # Don't keep a copy of the initial model.
  start_step = 0
  if config.restore_checkpoints:
    # Restore unreplicated optimizer + model state from last checkpoint.
    optimizer = checkpoints.restore_checkpoint(FLAGS.model_dir, optimizer)
    # Grab last step.
    start_step = int(optimizer.state.step)

  # Replicate optimizer.
  optimizer = jax_utils.replicate(optimizer)

  learning_rate_fn = train_utils.create_learning_rate_scheduler(
      factors=config.factors,
      base_learning_rate=learning_rate,
      warmup_steps=config.warmup)
  p_train_step = jax.pmap(
      functools.partial(train_step, learning_rate_fn=learning_rate_fn),
      axis_name='batch')
  p_eval_step = jax.pmap(eval_step, axis_name='batch')
  # p_pred_step = jax.pmap(predict_step, axis_name='batch')

  metrics_all = []
  tick = time.time()
  logging.info('Starting training')
  logging.info('====================')

  for step, batch in zip(range(start_step, num_train_steps), train_iter):
    batch = common_utils.shard(jax.tree_map(lambda x: x._numpy(), batch))  # pylint: disable=protected-access
    # logging.info(batch)
    optimizer, metrics, dropout_rngs = p_train_step(
        optimizer, batch, dropout_rng=dropout_rngs)
    metrics_all.append(metrics)
    logging.info('train in step: %d', step)

    # Save a Checkpoint
    if ((step % config.checkpoint_freq == 0 and step > 0) or
        step == num_train_steps - 1):
      if jax.host_id() == 0 and config.save_checkpoints:
        # Save unreplicated optimizer + model state.
        checkpoints.save_checkpoint(FLAGS.model_dir,
                                    jax_utils.unreplicate(optimizer), step)

    # Periodic metric handling.
    if step % eval_freq == 0 and step > 0:
      metrics_all = common_utils.get_metrics(metrics_all)
      lr = metrics_all.pop('learning_rate').mean()
      metrics_sums = jax.tree_map(jnp.sum, metrics_all)
      denominator = metrics_sums.pop('denominator')
      summary = jax.tree_map(lambda x: x / denominator, metrics_sums)  # pylint: disable=cell-var-from-loop
      summary['learning_rate'] = lr
      # Calculate (clipped) perplexity after averaging log-perplexities:
      summary['perplexity'] = jnp.clip(jnp.exp(summary['loss']), a_max=1.0e4)
      logging.info('train in step: %d, loss: %.4f, acc: %.4f', step,
                   summary['loss'], summary['accuracy'])
      if jax.host_id() == 0:
        tock = time.time()
        steps_per_sec = eval_freq / (tock - tick)
        tick = tock
        summary_writer.scalar('steps per second', steps_per_sec, step)
        for key, val in summary.items():
          summary_writer.scalar(f'train_{key}', val, step)
        summary_writer.flush()
      # Reset metric accumulation for next evaluation cycle.
      metrics_all = []

      # Eval Metrics
      eval_metrics = []
      eval_iter = iter(eval_ds)
      if num_eval_steps == -1:
        num_iter = itertools.repeat(1)
      else:
        num_iter = range(num_eval_steps)
      for _, eval_batch in zip(num_iter, eval_iter):
        # pylint: disable=protected-access
        eval_batch = common_utils.shard(
            jax.tree_map(lambda x: x._numpy(), eval_batch))
        # pylint: enable=protected-access
        metrics = p_eval_step(optimizer.target, eval_batch)
        eval_metrics.append(metrics)
      eval_metrics = common_utils.get_metrics(eval_metrics)
      eval_metrics_sums = jax.tree_map(jnp.sum, eval_metrics)
      eval_denominator = eval_metrics_sums.pop('denominator')
      eval_summary = jax.tree_map(
          lambda x: x / eval_denominator,  # pylint: disable=cell-var-from-loop
          eval_metrics_sums)
      # Calculate (clipped) perplexity after averaging log-perplexities:
      eval_summary['perplexity'] = jnp.clip(
          jnp.exp(eval_summary['loss']), a_max=1.0e4)
      logging.info('eval in step: %d, loss: %.4f, acc: %.4f', step,
                   eval_summary['loss'], eval_summary['accuracy'])
      if jax.host_id() == 0:
        for key, val in eval_summary.items():
          summary_writer.scalar(f'eval_{key}', val, step)
        summary_writer.flush()

      # Test eval
      # Eval Metrics
      logging.info('Testing...')
      test_metrics = []
      test_iter = iter(test_ds)
      if num_eval_steps == -1:
        num_iter = itertools.repeat(1)
      else:
        num_iter = range(num_eval_steps)
      for _, test_batch in zip(num_iter, test_iter):
        # pylint: disable=protected-access
        test_batch = common_utils.shard(
            jax.tree_map(lambda x: x._numpy(), test_batch))
        # pylint: enable=protected-access
        metrics = p_eval_step(optimizer.target, test_batch)
        test_metrics.append(metrics)
      test_metrics = common_utils.get_metrics(test_metrics)
      test_metrics_sums = jax.tree_map(jnp.sum, test_metrics)
      test_denominator = test_metrics_sums.pop('denominator')
      test_summary = jax.tree_map(
          lambda x: x / test_denominator,  # pylint: disable=cell-var-from-loop
          test_metrics_sums)
      # Calculate (clipped) perplexity after averaging log-perplexities:
      test_summary['perplexity'] = jnp.clip(
          jnp.exp(test_summary['loss']), a_max=1.0e4)
      logging.info('test in step: %d, loss: %.4f, acc: %.4f', step,
                   test_summary['loss'], test_summary['accuracy'])
      if jax.host_id() == 0:
        for key, val in test_summary.items():
          summary_writer.scalar(f'test_{key}', val, step)
        summary_writer.flush()


if __name__ == '__main__':
  app.run(main)
