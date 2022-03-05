XLA_PYTHON_CLIENT_ALLOCATOR=platform XLA_PYTHON_CLIENT_PREALLOCATE=false PYTHONPATH="$(pwd)":"$PYTHONPATH" python3 lra_benchmarks/text_classification/train.py \
      --config=lra_benchmarks/text_classification/configs/$1_base.py \
      --model_dir=/tmp/text_classification/$1 \
      --task_name=imdb_reviews \
