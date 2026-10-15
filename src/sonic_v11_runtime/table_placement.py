"""Explicit table placement adaptation; object and collisions are never changed."""
import math

def place_direct_table(table, front=.23):
    if not math.isfinite(front) or not .23 <= front <= .245:
        raise ValueError('Table front must be .23.. .245m; retain complete cube support')
    # Keep height, y extent and back edge (.87m) invariant. At .245m the
    # original 35mm cube centred at x=.267 still has4.5mm edge margin.
    if front == .23:
        table.set('pos','0.55 0 0.732')
        table.set('size','0.32 0.45 0.025')
    else:
        table.set('pos',f'{(.87+front)/2:.12g} 0 0.732')
        table.set('size',f'{(.87-front)/2:.12g} 0.45 0.025')
