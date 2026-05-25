import numpy as np


# 1. Samuelson's Inequality verification for ToneDriftRule
def verify_samuelson(n, threshold=2.0):
    # n-1 degrees of freedom standard deviation (ddof=1)
    # under Bessel's correction, the maximum deviation of any sample from the mean is:
    # max_dev <= s * (n - 1) / sqrt(n)
    max_z = (n - 1) / (n**0.5)
    possible = max_z > threshold
    print(
        f"n={n}: Max Z-score (deviation/std) possible is {max_z:.4f}. Can exceed threshold {threshold}? {possible}"
    )


print("--- 1. ToneDriftRule Samuelson Bound Verification ---")
for n in range(2, 8):
    verify_samuelson(n)


# 2. detect_action_discourse_gap logic verification
def detect_action_discourse_gap_mock(commitments, has_action):
    if len(commitments) < 3:
        return 0, 0.0, False

    repeats = 0
    max_repeats = 0
    last_comm = None

    for idx, comm in enumerate(commitments):
        action_taken = has_action[idx] if idx < len(has_action) else False
        if not action_taken and comm and (comm == last_comm or last_comm is None):
            repeats += 1
            max_repeats = max(max_repeats, repeats)
        else:
            repeats = 1 if not action_taken else 0
        last_comm = comm

    stalling_flag = max_repeats >= 3
    score = min(max_repeats / 10.0, 1.0)
    return max_repeats, score, stalling_flag


print("\n--- 2. Action-Discourse Gap Repetition Bug Verification ---")
comms = [None, "will implement", "will implement"]
actions = [False, False, False]
max_repeats, score, stalling = detect_action_discourse_gap_mock(comms, actions)
print(f"Commitments: {comms}")
print(
    f"Result repeats: {max_repeats} (Expected 2, got {max_repeats}) -> Stalling: {stalling}"
)


# 3. KL Divergence 1-element normalisation vulnerability
def kl_divergence_mock(p, q):
    epsilon = 1e-10
    p_arr = np.array(p) + epsilon
    q_arr = np.array(q) + epsilon

    p_arr = p_arr / np.sum(p_arr)
    q_arr = q_arr / np.sum(q_arr)

    return float(np.sum(p_arr * np.log(p_arr / q_arr)))


print("\n--- 3. KL Divergence Normalisation Vulnerability Verification ---")
# If observed only has one unique POS tag, say observed = [1.0] and expected = [0.05]
p = [1.0]
q = [0.05]
kl = kl_divergence_mock(p, q)
print(
    f"KL divergence between {p} and {q}: {kl} (Expected non-zero divergence, got {kl})"
)
