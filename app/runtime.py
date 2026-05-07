import os


def configure_runtime(thread_count: int) -> None:
    os.environ["OMP_NUM_THREADS"] = str(thread_count)
    os.environ["MKL_NUM_THREADS"] = str(thread_count)

    import torch

    torch.set_num_threads(thread_count)
