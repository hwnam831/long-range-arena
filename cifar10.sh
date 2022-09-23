XLA_PYTHON_CLIENT_PREALLOCATE=false XLA_PYTHON_CLIENT_ALLOCATOR=platform PYTHONPATH="$(pwd)":"$PYTHONPATH" python lra_benchmarks/image/train.py \
      --config=lra_benchmarks/image/configs/cifar10/$1_base.py \
      --model_dir=/tmp/image/$1 \
      --task_name=cifar10 