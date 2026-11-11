"""Environment backends: local process or isolated Docker container."""

from __future__ import annotations

from .protocol import TaskSpec


def make_env(spec: TaskSpec, backend: str = "local", *, mount_task_dir: bool = True):
    """Build an execution environment for a task.

    ``mount_task_dir=False`` is required for agent containers: the task directory holds
    ``gold.patch`` and ``test.patch``, and mounting it would let the agent read the answer.
    """
    if backend == "local":
        from minisweagent.environments.local import LocalEnvironment

        if spec.repo is None:
            raise ValueError(f"task {spec.id!r} has no repo; the local backend needs one")
        return LocalEnvironment(cwd=str(spec.repo), timeout=spec.timeout)

    if backend == "docker":
        from minisweagent.environments.docker import DockerEnvironment

        run_args = ["--rm"]
        if spec.task_dir is not None and mount_task_dir:
            run_args += ["-v", f"{spec.task_dir}:/rrl:ro"]
        if spec.mount_repo:
            run_args += ["-v", f"{spec.repo}:{spec.workdir}"]

        return DockerEnvironment(
            image=spec.image,
            cwd=spec.workdir,
            timeout=spec.timeout,
            run_args=run_args,
            env={
                # SWE-bench images ship a 2019-era certifi bundle, so any test that
                # talks to an HTTPS site fails with CERTIFICATE_VERIFY_FAILED even
                # when the gold patch is correct. The system bundle is current.
                "REQUESTS_CA_BUNDLE": "/etc/ssl/certs/ca-certificates.crt",
                "SSL_CERT_FILE": "/etc/ssl/certs/ca-certificates.crt",
            },
        )

    raise ValueError(f"unknown backend: {backend!r} (expected 'local' or 'docker')")
