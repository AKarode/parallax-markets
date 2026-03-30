import { useRef, useCallback, useState } from "react";
import type { HexCell } from "../types";

export function useHexData() {
  const dataRef = useRef<Map<string, HexCell>>(new Map());
  // Monotonic counter to trigger deck.gl re-render
  const [revision, setRevision] = useState(0);

  const updateCells = useCallback((cells: HexCell[]) => {
    for (const cell of cells) {
      dataRef.current.set(cell.cellId, cell);
    }
    // Bump revision to trigger deck.gl layer update
    setRevision((r) => r + 1);
  }, []);

  const getData = useCallback((): HexCell[] => {
    return Array.from(dataRef.current.values());
  }, []);

  return { updateCells, getData, revision };
}
