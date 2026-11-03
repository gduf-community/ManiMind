"""Tracked wave model: SI horizontal/time coordinates, centimetre displacement.

The native scenes and tests import these functions, not separate approximations.
The string is uniform, linear, nondispersive, and observed before reflections.
"""

import math


AMPLITUDE_CM = 1.0
WAVELENGTH_M = 4.0
PERIOD_S = 4.0
SPEED_M_S = WAVELENGTH_M / PERIOD_S
PULSE_HALF_WIDTH_M = 1.3
PULSE_CENTERS_M = (2.0, 8.0)
COLLISION_TIME_S = 3.0


def positive(value, name):
    if not math.isfinite(value) or value <= 0:
        raise ValueError(name + " must be finite and positive")
    return value


def wave_speed(wavelength_m=WAVELENGTH_M, period_s=PERIOD_S):
    return positive(wavelength_m, "wavelength") / positive(period_s, "period")


def harmonic(x_m, t_s, amplitude_cm=AMPLITUDE_CM,
             wavelength_m=WAVELENGTH_M, period_s=PERIOD_S):
    positive(wavelength_m, "wavelength")
    positive(period_s, "period")
    return amplitude_cm * math.cos(math.tau * (t_s / period_s - x_m / wavelength_m))


def harmonic_velocity(x_m, t_s):
    return -math.tau / PERIOD_S * AMPLITUDE_CM * math.sin(
        math.tau * (t_s / PERIOD_S - x_m / WAVELENGTH_M))


def smooth_start(u):
    u = min(1.0, max(0.0, u))
    return u ** 3 * (10 - 15 * u + 6 * u * u)


def source_displacement(t_s, ramp_s=1.0):
    positive(ramp_s, "ramp time")
    if t_s <= 0:
        return 0.0
    return smooth_start(t_s / ramp_s) * harmonic(0.0, t_s)


def forming_wave(x_m, t_s):
    if x_m < 0:
        raise ValueError("The driven half-string has x >= 0")
    return source_displacement(t_s - x_m / SPEED_M_S)


def particle_state(x_m, t_s, forming=False):
    return {"x_m": x_m, "y_cm": (forming_wave if forming else harmonic)(x_m, t_s)}


def crest_position(x_at_origin_m, t_s, origin_s=0.0):
    return x_at_origin_m + SPEED_M_S * (t_s - origin_s)


def spatial_snapshot(t_s, positions_m):
    return tuple((x, harmonic(x, t_s)) for x in positions_m)


def temporal_record(x_m, times_s):
    return tuple((t, harmonic(x_m, t)) for t in times_s)


def pulse_shape(offset_m, half_width_m=PULSE_HALF_WIDTH_M):
    u = offset_m / positive(half_width_m, "pulse half width")
    return (1 - u * u) ** 3 if abs(u) < 1 else 0.0


def pulse_gradient(offset_m, half_width_m=PULSE_HALF_WIDTH_M):
    u = offset_m / positive(half_width_m, "pulse half width")
    return -6 * u * (1 - u * u) ** 2 / half_width_m if abs(u) < 1 else 0.0


def pulse_centers(t_s):
    return (PULSE_CENTERS_M[0] + SPEED_M_S * t_s,
            PULSE_CENTERS_M[1] - SPEED_M_S * t_s)


def pulse_state(x_m, t_s, second_amplitude=1.0):
    first, second = pulse_centers(t_s)
    y1 = AMPLITUDE_CM * pulse_shape(x_m - first)
    y2 = second_amplitude * AMPLITUDE_CM * pulse_shape(x_m - second)
    vy1 = -SPEED_M_S * AMPLITUDE_CM * pulse_gradient(x_m - first)
    vy2 = SPEED_M_S * second_amplitude * AMPLITUDE_CM * pulse_gradient(x_m - second)
    return {"x_m": x_m, "t_s": t_s, "y1_cm": y1, "y2_cm": y2,
            "y_cm": y1 + y2, "vy_cm_s": vy1 + vy2,
            "centers_m": (first, second)}
