
#! Question i have heard about an app called judge 0 and there is somethng called c groups ??

'''
These are actually two different things that are often used together.

Judge0 is an online code execution system.
cgroups are a Linux kernel feature for limiting and isolating resources.

Judge0 uses technologies like cgroups to safely run untrusted user code.

Let's break it down.

What is Judge0?

Judge0 is an open-source online code execution engine.

Imagine you're building a website like:

LeetCode
HackerRank
Codeforces
Replit
Google Colab (partially)

A user writes:

print("Hello")

Clicks Run.

Your server executes it and returns:

Hello

Judge0 is the backend that does this.

Architecture:

Browser
      │
      ▼
Judge0 API
      │
      ▼
Execution Worker
      │
      ▼
Sandbox
      │
      ▼
Program Output

It supports dozens of languages like Python, C++, Java, Rust, Go, and JavaScript.

Why is this difficult?

Suppose someone submits:

while True:
    pass

Now your server CPU becomes stuck forever.

Or:

with open("/etc/passwd") as f:
    print(f.read())

Or:

import os

os.system("rm -rf /")

Clearly, you cannot let arbitrary user code run without restrictions.

You need a sandbox.

This is where cgroups come in

cgroups stands for:

Control Groups

It is a Linux kernel feature.

Think of it as giving each program a budget.

For example:

Program A

CPU:
20%

RAM:
256 MB

Disk:
100 MB

Time:
5 seconds

If the program exceeds its limits, the kernel can throttle or terminate it.

Example

Suppose a user writes:

x = []

while True:
    x.append("hello")

Without cgroups:

Program

↓

Consumes all RAM

↓

Entire server crashes

With cgroups:

Program

↓

Limited to 128 MB

↓

Kernel kills it

↓

Server remains healthy
What can cgroups limit?

A cgroup can limit many resources, including:

CPU usage
Memory (RAM)
Disk I/O
Network I/O (indirectly, often with other Linux features)
Number of processes
Process IDs (PIDs)

For example:

Container

RAM: 512 MB

CPU: 1 core

PIDs: 50

Disk: 100 MB

The kernel enforces these limits.

Does Docker use cgroups?

Yes.

This is one of Docker's most important building blocks.

When you run:

docker run --memory=512m --cpus=1 ubuntu

Docker configures cgroups so the container cannot exceed those limits.

So:

Docker
      │
      ▼
cgroups
      │
      ▼
Linux Kernel

Docker itself doesn't enforce the limits; it asks the Linux kernel to do it using cgroups.

Does Judge0 use Docker?

Typically, yes.

A simplified execution flow looks like:

User submits code
        │
        ▼
Judge0
        │
        ▼
Start Docker container
        │
        ▼
Apply cgroup limits
        │
        ▼
Run program
        │
        ▼
Collect output
        │
        ▼
Destroy container

So every submission runs in an isolated environment with strict resource limits.

Are cgroups the whole sandbox?

No.

A secure sandbox usually combines several Linux features:

Technology	Purpose
cgroups	Limit CPU, memory, processes, and other resources
Namespaces	Isolate processes, filesystems, networks, users, etc.
seccomp	Restrict which system calls a program can make
Capabilities	Remove unnecessary Linux privileges from processes
Containers (Docker, Podman, etc.)	Combine namespaces, cgroups, and other kernel features into an easy-to-use package
Why should you care as a backend engineer?

Many modern systems rely on these mechanisms:

Docker
Kubernetes
Judge0
GitHub Actions runners
Online IDEs
Cloud sandboxes
CI/CD systems

Understanding cgroups and namespaces gives you insight into how containers and secure execution environments actually work under the hood.

In fact, if you're interested in systems programming or backend
infrastructure, learning Linux namespaces first, then cgroups, and finally 
how Docker combines them is one of the most valuable paths to understanding container technology.


'''


