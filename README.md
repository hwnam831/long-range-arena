## Long-Range Arena + NAM.

This repositoriy is a forked version of google-reasearch/long-range-arena to benchmark neural attention memory

### Requirements

- CUDA 11.2 compatible GPU with more than 9GB VRAM (Tested on RTX 3080 10GB).
- Linux system with nvidia-driver/nvidia-docker installed.

### Docker and Dataset Setup


Pull the tensorflow-2.7.0 image `docker pull tensorflow/tensorflow:2.7.0-gpu`.

Download the dataset from [https://storage.googleapis.com/long-range-arena/lra_release.gz] (Note that this is actually a tar.gz file. Rename it to properly extract it).

Start the docker container while attaching this repository to `/lra` and the dataset directory to `/dataset` like below.  
`docker run -it --name=myflax --gpus all -v [this repository]:/lra -v [lra_release dataset directory]:/dataset tensorflow/tensorflow:2.7.0-gpu`

Go to `/lra` and install requirements py `pip install -r requirements.txt`.  
Install jaxlib by running `jaxlibinstall.sh`.  

### Dataset Setup


### Document Retrieval

Debug in progress. `document.sh` does not properly work yet.
<!--Download from aan dataset from [https://aan.how/download/#aanNetworkCorpus] and extract it to `./aan`.  -->
<!--Run `python lra_benchmarks/matching/build_vocab.py`.  -->


### Pathfinder

Debug in progress. `pathfinder.sh` does not properly work yet.