def print_fibonacci(n: int) -> None:
    """Print the first n numbers in the Fibonacci series."""
    a, b = 0, 1
    for _ in range(n):
        print(a, end=" ")
        a, b = b, a + b
    print()


if __name__ == "__main__":
    print_fibonacci(10)
