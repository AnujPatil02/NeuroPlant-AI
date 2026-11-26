"""
FFT bearing fault detection using CWRU vibration dataset.
Computes energy in fault-specific frequency bands:
BPFO (outer race), BPFI (inner race), BSF (ball), FTF (cage).
"""
import numpy as np
from scipy.io import loadmat
from scipy.fft import fft, fftfreq
from pathlib import Path

DATA_PATH = Path("data/raw/cwru")
SAMPLE_RATE = 12000  # Hz, standard CWRU drive-end sampling rate

# Bearing geometry constants (CWRU 6205-2RS JEM SKF bearing, drive end)
N_BALLS = 9
BALL_DIAMETER = 0.3126   # inches
PITCH_DIAMETER = 1.537   # inches
CONTACT_ANGLE = 0        # degrees, assume 0 for deep groove


def calculate_fault_frequencies(rpm: float) -> dict:
    """Compute BPFO, BPFI, BSF, FTF given shaft RPM and bearing geometry."""
    fr = rpm / 60  # shaft rotation frequency in Hz
    ratio = BALL_DIAMETER / PITCH_DIAMETER

    bpfo = (N_BALLS / 2) * fr * (1 - ratio)
    bpfi = (N_BALLS / 2) * fr * (1 + ratio)
    bsf = (PITCH_DIAMETER / (2 * BALL_DIAMETER)) * fr * (1 - ratio ** 2)
    ftf = (fr / 2) * (1 - ratio)

    return {"BPFO": bpfo, "BPFI": bpfi, "BSF": bsf, "FTF": ftf}


def load_vibration_signal(filepath: Path, key_prefix="DE"):
    """Load CWRU .mat file — extracts drive-end (DE) vibration channel."""
    mat = loadmat(str(filepath))
    key = [k for k in mat.keys() if key_prefix in k and "time" in k][0]
    return mat[key].flatten()


def compute_fft(signal: np.ndarray, sample_rate: int = SAMPLE_RATE):
    n = len(signal)
    yf = fft(signal)
    xf = fftfreq(n, 1 / sample_rate)[:n // 2]
    amplitude = 2.0 / n * np.abs(yf[:n // 2])
    return xf, amplitude


def band_energy(xf, amplitude, center_freq, bandwidth=5.0):
    """Sum energy in a frequency band around center_freq +/- bandwidth."""
    mask = (xf >= center_freq - bandwidth) & (xf <= center_freq + bandwidth)
    return float(np.sum(amplitude[mask] ** 2))


def diagnose_bearing_fault(filepath: Path, rpm: float = 1797):
    """
    Full pipeline: load signal -> FFT -> band energy -> compare to baseline.
    Returns dict with energy per fault band and diagnosed fault type.
    """
    signal = load_vibration_signal(filepath)
    xf, amplitude = compute_fft(signal)
    fault_freqs = calculate_fault_frequencies(rpm)

    energies = {
        name: band_energy(xf, amplitude, freq)
        for name, freq in fault_freqs.items()
    }

    dominant_fault = max(energies, key=energies.get)
    fault_map = {
        "BPFO": "Outer race fault",
        "BPFI": "Inner race fault",
        "BSF": "Ball/rolling element fault",
        "FTF": "Cage fault"
    }

    return {
        "energies": energies,
        "fault_frequencies_hz": fault_freqs,
        "diagnosis": fault_map[dominant_fault],
        "confidence_band": dominant_fault
    }


def compare_normal_vs_faulty(normal_file: Path, faulty_file: Path, rpm=1797):
    """Compares baseline (normal) vs a faulty file — shows relative energy rise."""
    normal_result = diagnose_bearing_fault(normal_file, rpm)
    faulty_result = diagnose_bearing_fault(faulty_file, rpm)

    print(f"\n{'Band':<8}{'Normal Energy':<18}{'Faulty Energy':<18}{'% Increase':<12}")
    print("-" * 56)
    for band in normal_result["energies"]:
        normal_e = normal_result["energies"][band]
        faulty_e = faulty_result["energies"][band]
        pct = ((faulty_e - normal_e) / normal_e * 100) if normal_e > 0 else 0
        print(f"{band:<8}{normal_e:<18.4f}{faulty_e:<18.4f}{pct:<12.1f}")

    print(f"\nDiagnosis: {faulty_result['diagnosis']} (dominant band: {faulty_result['confidence_band']})")
    return faulty_result


if __name__ == "__main__":
    # Update filenames to match your downloaded CWRU files
    normal_path = DATA_PATH / "Normal_0.mat"
    faulty_path = DATA_PATH / "IR007_0.mat"  # inner race fault example

    if normal_path.exists() and faulty_path.exists():
        compare_normal_vs_faulty(normal_path, faulty_path)
    else:
        print(f"Place CWRU .mat files in {DATA_PATH}")
        print("Download from: https://engineering.case.edu/bearingdatacenter/download-data-file")