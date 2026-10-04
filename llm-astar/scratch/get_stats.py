import json
import statistics

# E7
print('\n--- E7 Stats ---')
with open('experiments/results/experiment_7.json') as f:
    e7 = json.load(f)
densities = sorted(list(set(t['density'] for t in e7)))
for d in densities:
    exps = [t['llm_expanded'] for t in e7 if t['density'] == d]
    std_exps = [t['std_expanded'] for t in e7 if t['density'] == d]
    ratio = statistics.mean(exps) / statistics.mean(std_exps) if statistics.mean(std_exps) > 0 else 0
    print(f'Density: {d}, Ratio: {ratio:.2f}')

# E8
print('\n--- E8 Stats ---')
with open('experiments/results/experiment_8.json') as f:
    e8 = json.load(f)
sizes = sorted(list(set(t['size'] for t in e8)))
counts = sorted(list(set(t['count'] for t in e8)))
for s in sizes:
    for c in counts:
        fractions = [t['reprio_fraction'] for t in e8 if t['size'] == s and t['count'] == c]
        peaks = [t['peak_open'] for t in e8 if t['size'] == s and t['count'] == c]
        if fractions:
            print(f'Size: {s}, Count: {c}, Overhead: {statistics.mean(fractions)*100:.2f}%, Peak OPEN: {statistics.mean(peaks):.1f}')
