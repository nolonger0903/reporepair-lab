"""A code-repair agent loop with in-loop verification hooks.

Reuses mini-swe-agent's ``Model`` and ``Environment`` implementations but owns the
control flow, so we can attach verification, structured submission and richer
trajectory records.
"""

from __future__ import annotations

import time
import traceback
from typing import Any, Callable

from jinja2 import StrictUndefined, Template
from minisweagent.exceptions import FormatError, InterruptAgentFlow, LimitsExceeded, Submitted

from .protocol import StepRecord, Trajectory, VerifyResult

Verifier = Callable[[], VerifyResult]


def render(template: str, variables: dict[str, Any]) -> str:
    return Template(template, undefined=StrictUndefined).render(**variables)


class LoopAgent:
    def __init__(
        self,
        model,
        env,
        *,
        task_id: str,
        system_template: str,
        instance_template: str,
        step_limit: int = 30,
        cost_limit: float = 1.0,
        max_format_errors: int = 3,
        verifier: Verifier | None = None,
        verify_every: int = 0,
        on_step: Callable[[StepRecord], None] | None = None,
    ):
        self.model = model
        self.env = env
        self.task_id = task_id
        self.system_template = system_template
        self.instance_template = instance_template
        self.step_limit = step_limit
        self.cost_limit = cost_limit
        self.max_format_errors = max_format_errors
        self.verifier = verifier
        self.verify_every = verify_every
        self.on_step = on_step
        self.messages: list[dict] = []
        self.steps: list[StepRecord] = []
        self.cost = 0.0
        self.n_calls = 0

    def _template_vars(self, task: str) -> dict[str, Any]:
        return {"task": task, "n_calls": self.n_calls, "cost": self.cost}

    def _step(self, step: int, task: str) -> None:
        try:
            message = self.model.query(self.messages)
        except FormatError as e:
            # The call was billed before parsing failed.
            self.cost += e.messages[0].get("extra", {}).get("cost", 0.0)
            self.n_calls += 1
            raise
        self.n_calls += 1
        self.cost += message.get("extra", {}).get("cost", 0.0)
        self.messages.append(message)

        actions = message.get("extra", {}).get("actions", [])
        outputs = [self.env.execute(action) for action in actions]
        self.messages.extend(
            self.model.format_observation_messages(message, outputs, self._template_vars(task))
        )

        record = StepRecord(step=step, timestamp=time.time(), actions=actions, observations=outputs)
        if self.verifier and self.verify_every > 0 and step % self.verify_every == 0:
            record.verify = self.verifier()
        self.steps.append(record)
        if self.on_step:
            self.on_step(record)

    def run(self, task: str) -> Trajectory:
        start = time.time()
        self.messages = [
            self.model.format_message(role="system", content=render(self.system_template, self._template_vars(task))),
            self.model.format_message(role="user", content=render(self.instance_template, self._template_vars(task))),
        ]
        exit_status, submission = "MaxSteps", ""
        try:
            for step in range(1, self.step_limit + 1):
                if 0 < self.cost_limit <= self.cost:
                    raise LimitsExceeded(
                        {"role": "exit", "content": "LimitsExceeded", "extra": {"exit_status": "LimitsExceeded"}}
                    )
                self._step(step, task)
        except Submitted as e:
            self.messages.extend(e.messages)
            exit_status = "Submitted"
            submission = e.messages[0].get("extra", {}).get("submission", "")
        except LimitsExceeded as e:
            self.messages.extend(e.messages)
            exit_status = "LimitsExceeded"
        except FormatError as e:
            self.messages.extend(e.messages)
            exit_status = "FormatError"
        except InterruptAgentFlow as e:
            self.messages.extend(e.messages)
            exit_status = "Interrupted"
        except Exception as e:  # keep the trajectory even if the environment blows up
            self.messages.append(
                {
                    "role": "exit",
                    "content": str(e),
                    "extra": {"exit_status": type(e).__name__, "traceback": traceback.format_exc()},
                }
            )
            exit_status = "Error"

        final = self.verifier() if self.verifier else None
        return Trajectory(
            task_id=self.task_id,
            model=getattr(self.model.config, "model_name", "unknown"),
            messages=self.messages,
            steps=self.steps,
            final=final,
            exit_status=exit_status,
            submission=submission,
            cost=self.cost,
            n_calls=self.n_calls,
            duration_s=time.time() - start,
        )
