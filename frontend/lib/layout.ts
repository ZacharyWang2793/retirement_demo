// Grid layout helpers — find the next free slot for a newly-spawned card.

import type { CardLayout } from "./types";

export const GRID_COLS = 12;

// Default size per card_type. Cards not in this map use the fallback size.
export const CARD_SIZES: Record<string, { w: number; h: number }> = {
  balance_view: { w: 5, h: 7 },
  allocation_form: { w: 6, h: 12 },
  contribution_form: { w: 5, h: 7 },
  drift_view: { w: 6, h: 8 },
  confirmation: { w: 5, h: 6 },
  success: { w: 4, h: 5 },
  not_implemented: { w: 4, h: 4 },
  transaction_history: { w: 7, h: 8 },
  request_list: { w: 6, h: 7 },
  beneficiary_form: { w: 5, h: 9 },
  address_form: { w: 5, h: 9 },
  phone_form: { w: 4, h: 5 },
  email_form: { w: 4, h: 5 },
  name_form: { w: 5, h: 6 },
};

export const FALLBACK_SIZE = { w: 5, h: 7 };

export function sizeFor(cardType: string): { w: number; h: number } {
  return CARD_SIZES[cardType] ?? FALLBACK_SIZE;
}

/**
 * Find the next free top-left slot in a grid of GRID_COLS columns that fits a
 * (w, h) rectangle without overlapping any layout item. Searches row-major.
 */
export function findNextFreeSlot(
  layout: CardLayout[],
  w: number,
  h: number,
  cols: number = GRID_COLS
): { x: number; y: number } {
  // Build an occupancy set: each cell (x, y) covered by an existing card.
  const occupied = new Set<string>();
  let maxY = 0;
  for (const item of layout) {
    for (let dx = 0; dx < item.w; dx++) {
      for (let dy = 0; dy < item.h; dy++) {
        occupied.add(`${item.x + dx},${item.y + dy}`);
      }
    }
    maxY = Math.max(maxY, item.y + item.h);
  }

  const maxSearchY = maxY + h; // never need to look past one card-height below the lowest existing card

  for (let y = 0; y <= maxSearchY; y++) {
    for (let x = 0; x + w <= cols; x++) {
      let fits = true;
      for (let dx = 0; dx < w && fits; dx++) {
        for (let dy = 0; dy < h && fits; dy++) {
          if (occupied.has(`${x + dx},${y + dy}`)) fits = false;
        }
      }
      if (fits) return { x, y };
    }
  }
  // Fallback — should never hit because of maxSearchY bound
  return { x: 0, y: maxY };
}
