XLA_PYTHON_CLIENT_ALLOCATOR=platform XLA_PYTHON_CLIENT_PREALLOCATE=false PYTHONPATH="$(pwd)":"$PYTHONPATH" python3 lra_benchmarks/matching/train.py \
      --config=lra_benchmarks/matching/configs/$1_base.py \
      --model_dir=/tmp/document/$1 \
      --task_name=aan \
      --data_dir=/lra/lra_release/lra_release/tsv_data
