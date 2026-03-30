import { useMemo } from "react";
import DeckGL from "@deck.gl/react";
import { H3HexagonLayer } from "@deck.gl/geo-layers";
import { Map } from "react-map-gl/maplibre";
import type { HexCell } from "../types";
import { influenceToColor } from "../lib/colors";

const MAPLIBRE_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const INITIAL_VIEW = {
  longitude: 54.5,
  latitude: 25.5,
  zoom: 6,
  pitch: 30,
  bearing: 0,
};

interface Props {
  getData: () => HexCell[];
  revision: number;
}

export function HexMap({ getData, revision }: Props) {
  const layers = useMemo(() => {
    const data = getData();
    return [
      new H3HexagonLayer({
        id: "hex-layer",
        data,
        getHexagon: (d: HexCell) => d.cellId,
        getFillColor: (d: HexCell) => influenceToColor(d.influence),
        getElevation: (d: HexCell) => d.threatLevel * 1000,
        extruded: true,
        elevationScale: 1,
        opacity: 0.7,
        pickable: true,
        transitions: {
          getFillColor: 600,
        },
        updateTriggers: {
          getFillColor: [revision],
          getElevation: [revision],
        },
      }),
    ];
  }, [getData, revision]);

  return (
    <DeckGL
      initialViewState={INITIAL_VIEW}
      controller
      layers={layers}
      style={{ width: "100%", height: "100%" }}
    >
      <Map mapStyle={MAPLIBRE_STYLE} />
    </DeckGL>
  );
}
