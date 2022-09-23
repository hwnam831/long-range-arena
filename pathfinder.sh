_PATHFINER_TFDS_PATH=/lra/lra_release/lra_release/pathfinder32 XLA_PYTHON_CLIENT_PREALLOCATE=false XLA_PYTHON_CLIENT_ALLOCATOR=platform PYTHONPATH="$(pwd)":"$PYTHONPATH" python lra_benchmarks/image/train.py \
      --config=lra_benchmarks/image/configs/pathfinder32/$1_base.py \
      --model_dir=/tmp/pathfinder32/$1 \
      --task_name=pathfinder32_hard 