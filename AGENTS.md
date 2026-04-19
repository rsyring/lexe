# System Changes / Agent Permissions

IMPORTANT: the files you edit should only be in this local repo, NEVER anywhere else on the system.

You, the agent, should NEVER run commands on the system that would make permanent changes.  We
ALWAYS put our action plan into code or IAC before applying to the system.

You are ONLY ALLOWED to run READ-ONLY cli commands.

If you are ever confused about what you have permission to do, stop and ask.

## Exceptions

1. You ARE PERMITTED to run `uv add` commands in response to user instructions.

## `ssh exe.dev` safety

You are granted limited permissions to use `ssh exe.dev` which is working against a live paid service running real apps.

You may ONLY run destructive commands against exe.dev when it is for one of our apps in the `./examples` folder.


# Conditional Instructions Index

1. At the start of every session, before responding to the first user prompt or doing any
   task-related work, you MUST ALWAYS load the [index
   file](https://raw.githubusercontent.com/rsyring/agent-configs/refs/heads/main/conditional-instructions.yaml)
2. You MUST NOT load any linked documents from that index UNLESS that document's `when` condition
   applies to the current task.
3. If the index file cannot be fetched, stop and report that failure before answering the user
   substantively.
4. WHEN you load a document from the index, notify the user.


# Specs

Do not duplicate implementation details or exact commands into spec documents when the code is the
source of truth. Keep specs focused on decisions, scope, open questions, and validation outcomes so
they do not become stale mirrors of the implementation.


# Python Style

We want modern Python style with a preference for dataclasses and object oriented behaviors on those classes when warranted.

Avoid creating a lot of top-level functions when the logic is associated with it's data and should be on the class.

