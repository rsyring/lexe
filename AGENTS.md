# System Changes / Agent Permissions

IMPORTANT: the files you edit should only be in this local repo, NEVER anywhere else on the system.

You, the agent, should NEVER run commands on the system that would make permanent changes.  We
ALWAYS put our action plan into code or IAC before applying to the system.

You are ONLY ALLOWED to run READ-ONLY cli commands.

If you are ever confused about what you have permission to do, stop and ask.

# Conditional Instructions Index

1. At the start of every session, before responding to the first user prompt or doing any
   task-related work, you MUST ALWAYS load the [index
   file](https://raw.githubusercontent.com/rsyring/agent-configs/refs/heads/main/conditional-instructions.yaml)
2. You MUST NOT load any linked documents from that index UNLESS that document's `when` condition
   applies to the current task.
3. If the index file cannot be fetched, stop and report that failure before answering the user
   substantively.
