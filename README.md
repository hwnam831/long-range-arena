# Long-Range Arena + NAM.

This repositoriy is a forked version of google-reasearch/long-range-arena to benchmark neural attention memory

## Requirements

- CUDA 11 compatible GPU with more than 9GB VRAM (Tested on RTX 3080 10GB).
- Linux system with nvidia-driver and nvidia-docker installed.

## Docker and Dataset Setup

- Pull the tensorflow-2.7.0 image `docker pull tensorflow/tensorflow:2.7.0-gpu`.
- Download the dataset from [https://storage.googleapis.com/long-range-arena/lra_release.gz] (This is actually a tar.gz file. Rename it extract properly).
- Start the docker container while attaching this repository to `/lra` and the dataset directory to `/dataset` like below.  
`docker run -it --name=myflax --gpus all -v [this repository]:/lra -v [lra_release dataset directory]:/dataset tensorflow/tensorflow:2.7.0-gpu`
- Go to `/lra` and install requirements py `pip install -r requirements.txt`.  
- Install jaxlib by running `jaxlibinstall.sh`.  

## ListOps, Text Classification, and Pixel-level Image Classification

The tasks can run without any modification.  
Use the pre-defined scripts to run them.  
- Ex1) Image classification with Transformer: `./cifar10 transformer`
- Ex2) ListOps with NAM Transformer: `./cifar10 nam_transformer`
- Ex3) Text classification with Linear Transformer: `./cifar10 linear_transformer`  

Only tested with those three transformers, but it is possible to run with others.

## Document Retrieval

Debug in progress. `document.sh` does not properly work yet.
<!--Download from aan dataset from [https://aan.how/download/#aanNetworkCorpus] and extract it to `./aan`.  -->
<!--Run `python lra_benchmarks/matching/build_vocab.py`.  -->


## Pathfinder

Debug in progress. `pathfinder.sh` does not properly work yet.

## Results

The tensorboard results are recorded under `/tmp` directory.