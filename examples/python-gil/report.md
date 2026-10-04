# How does the Python GIL affect CPU-bound multithreaded programs?

_Status: budget_exhausted. 8 of 12 proposed claims verified; 4 rejected by the citation verifier._

_Budget caps hit: fetch._

In standard CPython, the Global Interpreter Lock (GIL) restricts execution so that only one thread can run Python bytecode at a time [^1]. This limitation means that parallel CPU execution is constrained when using multithreading [^2]. Consequently, the GIL prevents true parallelism in CPU-bound multithreaded programs, resulting in performance that is similar to or slightly slower than single-threaded execution [^3]. Because of this, multithreading is generally not suitable for speeding up CPU-bound Python code [^4]. Although CPython periodically releases the GIL to allow other threads to execute, with a default switch interval of 5 milliseconds that is tunable via sys.setswitchinterval(), this does not enable true parallelism for CPU-bound tasks [^5]. Instead, multiprocessing is best suited for CPU-bound tasks, whereas multithreading is best suited for I/O-bound tasks [^6]. Multiprocessing allows for true parallel execution of CPU-bound workloads because separate processes can run on different CPU cores [^7]. In a multiprocessing setup, each process has its own GIL, allowing work to be distributed across multiple processes [^8].

[^1]: "In standard CPython, GIL (Global Interpreter Lock) allows only one thread to execute Python bytecode at a time." - https://www.geeksforgeeks.org/python/difference-between-multithreading-vs-multiprocessing-in-python/
[^2]: "Parallel CPU execution | Limited in standard CPython | Supported" - https://www.geeksforgeeks.org/python/difference-between-multithreading-vs-multiprocessing-in-python/
[^3]: "In a CPU-bound task, multiple threads do NOT run in parallel because the GIL does not allow it." - https://www.geeksforgeeks.org/python/what-is-the-python-global-interpreter-lock-gil/; "Eight worker threads. Should be a lot faster, right? It was the same speed. Maybe a hair slower." - https://dev.to/lovestaco/how-pythons-gil-actually-works-and-when-it-bites-you-3f2
[^4]: "Therefore, Multithreading is generally not suitable for speeding up CPU-bound Python code." - https://www.geeksforgeeks.org/python/difference-between-multithreading-vs-multiprocessing-in-python/
[^5]: "CPython periodically gives other waiting threads a chance to acquire the GIL (the interval is 5 ms by default, tunable via sys.setswitchinterval())" - https://dev.to/lovestaco/how-pythons-gil-actually-works-and-when-it-bites-you-3f2
[^6]: "Best suited for | I/O-bound tasks | CPU-bound tasks" - https://www.geeksforgeeks.org/python/difference-between-multithreading-vs-multiprocessing-in-python/
[^7]: "Separate processes can run on different CPU cores, they can achieve true parallel execution." - https://www.geeksforgeeks.org/python/difference-between-multithreading-vs-multiprocessing-in-python/
[^8]: "Unlike, threads here each process has its own GIL, so work can be distributed across multiple processes." - https://www.geeksforgeeks.org/python/difference-between-multithreading-vs-multiprocessing-in-python/

## Under-covered topics

- Performance Impact on CPU-Bound Tasks (0 verified)
