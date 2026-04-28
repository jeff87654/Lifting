"""
Enumerate FPF partitions of 15 (partitions with all parts >= 2)
and estimate computational difficulty for the lifting algorithm.
"""

def partitions_of_n_min_part(n, min_part=2, max_part=None):
    """
    Generate all partitions of n where all parts >= min_part.
    Yields partitions in lexicographic order (largest parts first).
    """
    if max_part is None:
        max_part = n
    
    if n == 0:
        yield []
        return
    
    for i in range(min(n, max_part), min_part - 1, -1):
        for p in partitions_of_n_min_part(n - i, min_part, i):
            yield [i] + p


def estimate_difficulty(partition):
    """
    Estimate relative difficulty of computing classes for this partition.
    
    Factors:
    - Number of parts: more parts = more lifting layers = harder
    - Repeated parts: repeated parts create larger invariant buckets = harder
    - Product of parts: larger product = larger chief factors = harder
    - Ratio of max to min: unbalanced = more complex factorization patterns
    """
    
    if not partition:
        return 0.0
    
    num_parts = len(partition)
    
    # Count repetitions (unique value counts)
    from collections import Counter
    part_counts = Counter(partition)
    num_unique = len(part_counts)
    max_repetition = max(part_counts.values())
    has_repeats = 1 if max_repetition > 1 else 0
    
    # Product of parts (proxy for chief factor sizes)
    product = 1
    for p in partition:
        product *= p
    
    # Ratio of max to min (balance)
    max_part = max(partition)
    min_part = min(partition)
    balance_ratio = max_part / min_part
    
    # Base difficulty from number of parts (lifting layers)
    base_difficulty = num_parts ** 1.5
    
    # Repetition penalty (creates larger buckets)
    repetition_penalty = 1.0 + (2.0 * has_repeats) + (0.5 * (max_repetition - 1))
    
    # Product penalty (larger chief factors)
    log_product = 1.0 + (product / 100.0)  # Normalize: product 100 = 1x difficulty
    
    # Balance penalty (unbalanced partitions harder)
    balance_penalty = 1.0 + (0.3 * (balance_ratio - 1.0))
    
    # Combine: parts are most important, then repeats, then product
    difficulty = base_difficulty * repetition_penalty * log_product * balance_penalty
    
    return difficulty


def format_partition(partition):
    """Format partition as [a,b,c,...]"""
    return "[" + ",".join(str(p) for p in partition) + "]"


def main():
    print("=" * 90)
    print("FPF Partitions of 15 (all parts >= 2)")
    print("=" * 90)
    print()
    
    # Enumerate all FPF partitions
    partitions = list(partitions_of_n_min_part(15, min_part=2))
    
    # Add difficulty estimates
    difficulty_data = []
    for p in partitions:
        difficulty = estimate_difficulty(p)
        difficulty_data.append((p, difficulty))
    
    # Sort by difficulty (descending)
    difficulty_data.sort(key=lambda x: x[1], reverse=True)
    
    # Print count
    print(f"Total FPF partitions of 15: {len(partitions)}")
    print()
    
    # Print all partitions (unsorted first for reference)
    print("All FPF partitions (lexicographic order):")
    for i, p in enumerate(partitions, 1):
        print(f"  {i:2d}. {format_partition(p)}")
    
    print()
    print("=" * 90)
    print("Sorted by Estimated Difficulty (hardest first)")
    print("=" * 90)
    print()
    
    # Header
    header = f"{'Rank':>4} {'Partition':>20} {'Parts':>5} {'Repeats':>7} {'Product':>8} {'Balance':>7} {'Difficulty':>12}"
    print(header)
    print("-" * 90)
    
    for rank, (partition, difficulty) in enumerate(difficulty_data, 1):
        # Compute stats for display
        num_parts = len(partition)
        
        from collections import Counter
        part_counts = Counter(partition)
        num_repeats = sum(1 for count in part_counts.values() if count > 1)
        max_rep = max(part_counts.values()) if part_counts else 1
        
        product = 1
        for p in partition:
            product *= p
        
        max_part = max(partition)
        min_part = min(partition)
        balance_ratio = max_part / min_part
        
        repeat_str = f"Yes({max_rep}x)" if num_repeats > 0 else "No"
        balance_str = f"{balance_ratio:.1f}"
        
        partition_str = format_partition(partition)
        
        print(f"{rank:4d} {partition_str:>20} {num_parts:5d} {repeat_str:>7} {product:8d} {balance_str:>7} {difficulty:12.2f}")
    
    print()
    print("=" * 90)
    print("Legend:")
    print("  Parts: Number of parts in partition (more = more lifting layers)")
    print("  Repeats: Whether parts repeat (yes = harder dedup, larger buckets)")
    print("  Product: Product of parts (larger = larger chief factors)")
    print("  Balance: Ratio max/min part (larger = more complex factorizations)")
    print("  Difficulty: Combined score (higher = harder computation expected)")
    print("=" * 90)


if __name__ == "__main__":
    main()
