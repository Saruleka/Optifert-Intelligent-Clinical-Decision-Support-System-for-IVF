import os
import sys
import numpy as np
import pandas as pd

# Add the workspace directory to the path so we can import model functions
sys.path.append(r'd:\Downloads\ml_model')

from model import (
    compute_tdps, label_timing, label_ohss, estimate_mii, inject_label_noise
)

def inject_measurement_noise_balanced(df, rng):
    """
    Balanced clinical measurement noise (High-standard clinic with solid quality controls):
      - E2 assay:         ±4% CV (log-normal, standard lab)
      - Follicle count:   negligible error (1% chance of ±1 follicle)
      - Lead follicle:    ±0.4 mm (standardized ultrasound)
      - LH:               ±5% (lab assay)
      - Growth:           ±0.08 mm/day
      - AMH:              ±3% (recalibrated assay)
      - BMI:              ±0.08
    """
    df = df.copy()
    n  = len(df)

    df['e2']           = (df['e2']    * rng.lognormal(0, 0.04, n)).clip(100, 12000).round()
    df['e2_prev']      = (df['e2_prev'] * rng.lognormal(0, 0.04, n)).clip(50, 8000).round()
    df['lh']           = (df['lh']    * rng.lognormal(0, 0.05, n)).clip(0.1, 20).round(1)
    df['amh']          = (df['amh']   * rng.lognormal(0, 0.03, n)).clip(0.1, 15).round(1)
    df['growth']       = (df['growth'] + rng.normal(0, 0.08, n)).clip(0, 5).round(1)
    df['bmi']          = (df['bmi']   + rng.normal(0, 0.08, n)).clip(16, 40).round(1)
    df['lead_follicle']= (df['lead_follicle'] + rng.normal(0, 0.4, n)).clip(10, 30).round().astype(int)

    # Follicle counts: negligible integer noise (1% chance of shift)
    f12_noise = rng.choice([-1, 0, 1], size=n, p=[0.005, 0.99, 0.005])
    df['f12'] = (df['f12'] + f12_noise).clip(0, 35)
    df['f18'] = df.apply(lambda r: min(r.f18, r.f12), axis=1)
    df['f22'] = df.apply(lambda r: min(r.f22, r.f12 - r.f18), axis=1)

    return df

def generate_balanced_synthetic_data(n=8000, seed=42):
    """
    Clinically realistic IVF synthetic dataset with balanced (moderate) noise levels.
    """
    rng = np.random.default_rng(seed)

    # Patient archetypes
    profile = rng.choice(['poor', 'normal', 'hyper'], n, p=[0.2, 0.6, 0.2])
    age = rng.integers(22, 45, n)

    amh = []
    afc = []

    for i in range(n):
        if profile[i] == 'poor':
            a = rng.normal(1.2, 0.5)
            f = rng.integers(4, 10)
        elif profile[i] == 'hyper':
            a = rng.normal(5.5, 1.5)
            f = rng.integers(18, 30)
        else:  # normal
            a = rng.normal(3.0, 1.2)
            f = rng.integers(8, 20)

        amh.append(np.clip(a, 0.2, 10))
        afc.append(f)

    amh = np.array(amh)
    afc = np.array(afc)
    bmi = rng.normal(23.5, 3, n).clip(17, 35)

    protocol = rng.choice(['agonist', 'antagonist', 'mild'], n, p=[0.5, 0.45, 0.05])
    gon = rng.choice([150, 225, 300], n, p=[0.3, 0.5, 0.2])
    stim_days = rng.integers(8, 13, n)

    # Follicular response
    f12 = np.clip((afc * rng.uniform(0.6, 1.0, n)).astype(int), 3, 30)
    f18 = np.clip((f12 * rng.uniform(0.25, 0.5, n)).astype(int), 0, 15)
    f22 = np.clip((f12 * rng.uniform(0.05, 0.15, n)).astype(int), 0, 5)

    lead_follicle = np.clip(
        rng.normal(17 + 0.4 * stim_days, 2, n), 14, 26
    ).astype(int)

    # Hormones
    e2_per_fol = []
    for i in range(n):
        if profile[i] == 'hyper':
            val = rng.normal(300, 60)
        elif profile[i] == 'poor':
            val = rng.normal(180, 40)
        else:
            val = rng.normal(220, 50)
        e2_per_fol.append(np.clip(val, 120, 450))

    e2_per_fol = np.array(e2_per_fol)
    e2 = (f12 * e2_per_fol).clip(300, 6000)
    e2_prev = e2 / rng.uniform(1.3, 2.2, n)

    lh = rng.normal(2, 1, n).clip(0.3, 8)
    growth = rng.normal(1.6, 0.5, n).clip(0.5, 3)

    df = pd.DataFrame({
        'age': age,
        'bmi': bmi.round(1),
        'amh': amh.round(2),
        'afc': afc,
        'protocol': protocol,
        'gon': gon,
        'stim_days': stim_days,
        'f12': f12,
        'f18': f18,
        'f22': f22,
        'lead_follicle': lead_follicle,
        'e2': e2.round(),
        'e2_prev': e2_prev.round(),
        'lh': lh.round(2),
        'growth': growth.round(2),
    })

    # Clean labels (ground truth)
    df['timing_label'] = df.apply(label_timing, axis=1)
    df['ohss_label']   = df.apply(label_ohss, axis=1)
    df['mii_estimate'] = df.apply(estimate_mii, axis=1)

    # Inject balanced noise
    df = inject_measurement_noise_balanced(df, rng)
    df = inject_label_noise(df, rng, base_flip=0.01, grey_zone_flip=0.03)

    return df.sample(frac=1, random_state=42).reset_index(drop=True)

if __name__ == '__main__':
    print("Generating balanced synthetic dataset (n=8000)...")
    df = generate_balanced_synthetic_data(n=8000, seed=42)
    
    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, 'ivf_synthetic_dataset.csv')
    df.to_csv(output_path, index=False)
    
    print(f"Dataset successfully generated and saved to: {output_path}")
    print(f"Dataset shape: {df.shape}")
    print("\nTiming label distribution:")
    print(df['timing_label'].value_counts())
    print("\nOHSS label distribution:")
    print(df['ohss_label'].value_counts())
