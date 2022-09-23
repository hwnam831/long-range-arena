XLA_PYTHON_CLIENT_PREALLOCATE=false XLA_PYTHON_CLIENT_ALLOCATOR=platform PYTHONPATH="$(pwd)":"$PYTHONPATH" python lra_benchmarks/listops/train.py \
      --config=lra_benchmarks/listops/configs/$1_base.py \
      --model_dir=/tmp/listops/$1 \
      --task_name=basic \
      --data_dir=/dataset/listops-1000/