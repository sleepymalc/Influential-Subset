import warnings
warnings.filterwarnings("ignore")

import numpy as np

from actual import actual
from IWLS import IWLS, adaptive_IWLS
from first_order import first_order, adaptive_first_order
from margin import margin
from utility import data_generation, actual_rank, get_args

if __name__ == '__main__':
    args = get_args()

    # general parameters
    n = args.n
    d = args.d
    k = args.k
    job_n = args.job_n
    cov = args.cov
    isSkewed = args.skewed
    target = args.target
    seed = args.seed

    assert target in ["probability", "abs_probability", "test_loss", "abs_test_loss", "avg_abs_test_loss", "abs_avg_test_loss"], f'Invalid target: {target}'

    out_file = f"results/target={target}/n={n}_d={d}_k={k}/s={seed}_cov={cov}.txt"

    X_train, y_train, X_test, y_test = data_generation(n, d, cov, seed, isSkewed=isSkewed, target=target)

    print_size = k * 2

    # Best Subset
    score, best_subset = actual(X_train, y_train, X_test, y_test, k=k, job_n=job_n, target=target)
    best_k_score = score[-1]

    with open(out_file, 'w') as f:
        f.write('Best Subset\n')
        for subset_size in range(1, k + 1):
            f.write(f"\tsize {subset_size}: {best_subset[subset_size-1]}\n")
        f.write('\n')

    # IWLS
    IWLS_best = IWLS(X_train, y_train, X_test, y_test, target=target)
    with open(out_file, 'a') as f:
        f.write('IWLS Best Subset\n')
        f.write(f"\ttop {print_size}: {IWLS_best[:print_size]}\n\n")

    # Adaptive IWLS
    adaptive_IWLS_best_k = adaptive_IWLS(X_train, y_train, X_test, y_test, k=k, target=target)
    with open(out_file, 'a') as f:
        f.write('Adaptive IWLS Best Subset\n')
        f.write(f"\ttop {k}: {adaptive_IWLS_best_k}\n\n")

    # Margin-based approach
    ind_n, ind_p = margin(X_train, y_train)
    with open(out_file, 'a') as f:
        f.write('Margin-based Best Subset\n')
        f.write(f"\tpositive group:\ttop {print_size}: {ind_p[:print_size]}\n")
        f.write(f"\tnegative group:\ttop {print_size}: {ind_n[:print_size]}\n\n")

    # First-order method
    FO_best = first_order(X_train, y_train, X_test, y_test, target=target)
    with open(out_file, 'a') as f:
        f.write('First-order Best Subset\n')
        f.write(f"\ttop {print_size}: {FO_best[:print_size]}\n\n")

    # Adaptive First-order method
    adaptive_FO_best = adaptive_first_order(X_train, y_train, X_test, y_test, target=target)
    with open(out_file, 'a') as f:
        f.write('Adaptive First-order Best Subset\n')
        f.write(f"\ttop {print_size}: {adaptive_FO_best[:print_size]}\n\n")

    with open(out_file, 'a') as f:
        f.write('IWLS Best Subset v.s. Best Subset (size=k)\n')
        rank = actual_rank(X_train, y_train, X_test, y_test, IWLS_best[:k], best_k_score, target=target)
        f.write(f'\tActual rank: {rank}\n\n')


        f.write('Adaptive IWLS Best Subset v.s. Best Subset (size=k)\n')
        rank = actual_rank(X_train, y_train, X_test, y_test, adaptive_IWLS_best_k, best_k_score, target=target)
        f.write(f'\tActual rank: {rank}\n\n')


        f.write('Margin-based Best Subset v.s. Best Subset (size=k)\n')
        f.write(f'P Group\n')
        rank = actual_rank(X_train, y_train, X_test, y_test, ind_p[:k], best_k_score, target=target)
        f.write(f'\tActual rank: {rank}\n')

        f.write(f'N Group\n')
        rank = actual_rank(X_train, y_train, X_test, y_test, ind_n[:k], best_k_score, target=target)
        f.write(f'\tActual rank: {rank}\n\n')

        f.write('First-order Best Subset v.s. Best Subset (size=k)\n')
        rank = actual_rank(X_train, y_train, X_test, y_test, FO_best[:k], best_k_score, target=target)
        f.write(f'\tActual rank: {rank}\n\n')


        f.write('Adaptive First-order Best Subset v.s. Best Subset (size=k)\n')
        rank = actual_rank(X_train, y_train, X_test, y_test, adaptive_FO_best[:k], best_k_score, target=target)
        f.write(f'\tActual rank: {rank}\n')