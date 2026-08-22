"""AERIX — Road Network & Lane Topology Engine

Binds vehicle trajectories to the physical roadway network:
- Road Links (Corridors: North, South, East, West)
- Approaches (Inbound vs Outbound)
- Lanes (Lane 1 [Fast/Inner], Lane 2 [Center], Lane 3 [Curb/Slow], Dedicated Turn Pockets)
- Moment-to-moment trajectory lane snapping
- Map-Native Desire Lines over real geometry
- Queue Extents drawn along the actual carriageway centerline
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Union
import numpy as np


@dataclass
class RoadLane:
    """Represents a single physical traffic lane on a roadway link."""
    lane_id: str
    link_id: str
    approach: str  # 'Inbound' or 'Outbound'
    lane_index: int  # 1 = leftmost / fast lane, 2 = center, etc.
    lane_type: str  # 'through', 'left_turn', 'right_turn', 'general'
    centerline_coords: List[List[float]]  # [[lon, lat], [lon, lat], ...]
    polygon_coords: List[List[float]]  # Polygon bounding the lane
    width_meters: float = 3.5
    speed_limit_kmh: float = 50.0

    def to_geojson_feature(self, metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Export lane geometry as a GeoJSON Feature."""
        props = {
            "lane_id": self.lane_id,
            "link_id": self.link_id,
            "approach": self.approach,
            "lane_index": self.lane_index,
            "lane_type": self.lane_type,
            "speed_limit_kmh": self.speed_limit_kmh,
        }
        if metrics:
            props.update(metrics)

        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [self.polygon_coords]
            },
            "properties": props
        }


@dataclass
class RoadLink:
    """Represents a roadway link/corridor leading to or from an intersection."""
    link_id: str
    name: str
    cardinal_direction: str  # 'North', 'South', 'East', 'West'
    bearing_deg: float  # direction of inbound travel
    inbound_lanes: List[RoadLane] = field(default_factory=list)
    outbound_lanes: List[RoadLane] = field(default_factory=list)


@dataclass
class IntersectionApproach:
    """Represents an intersection approach gate for O-D movements."""
    approach_id: str
    name: str
    cardinal: str
    centroid_lat: float
    centroid_lon: float


class RoadNetworkModel:
    """Constructs and manages the geographic road network topology and trajectory binding."""

    EARTH_RADIUS = 6378137.0

    def __init__(
        self,
        center_lat: float = 37.774929,
        center_lon: float = -122.419416,
        arm_length_meters: float = 120.0,
        lane_width_meters: float = 3.5,
        num_lanes_per_direction: int = 2,
    ):
        """Initialize road network centered on intersection GPS.

        Args:
            center_lat: Intersection center latitude
            center_lon: Intersection center longitude
            arm_length_meters: Length of each approach corridor in meters
            lane_width_meters: Standard lane width in meters
            num_lanes_per_direction: Number of lanes per inbound/outbound carriageway
        """
        self.center_lat = center_lat
        self.center_lon = center_lon
        self.arm_len = arm_length_meters
        self.lane_w = lane_width_meters
        self.num_lanes = num_lanes_per_direction

        self.links: Dict[str, RoadLink] = {}
        self.lanes: Dict[str, RoadLane] = {}
        self.approaches: Dict[str, IntersectionApproach] = {}

        self._build_standard_4way_network()

    def _offset_gps(self, ref_lat: float, ref_lon: float, east_m: float, north_m: float) -> Tuple[float, float]:
        """Compute offset GPS coordinate from metric displacement."""
        lat_rad = math.radians(ref_lat)
        d_lat = (north_m / self.EARTH_RADIUS) * (180.0 / math.pi)
        d_lon = (east_m / (self.EARTH_RADIUS * math.cos(lat_rad))) * (180.0 / math.pi)
        return (ref_lat + d_lat, ref_lon + d_lon)

    def _build_standard_4way_network(self) -> None:
        """Construct a 4-leg intersection road network geometry."""
        # 4 Links: North (0 deg), East (90 deg), South (180 deg), West (270 deg)
        configs = [
            ("north", "North Arterial", "North", 180.0, (0.0, 1.0), (1.0, 0.0)),
            ("south", "South Boulevard", "South", 0.0,   (0.0, -1.0), (-1.0, 0.0)),
            ("east",  "East Avenue",    "East",  270.0, (1.0, 0.0), (0.0, -1.0)),
            ("west",  "West Parkway",   "West",  90.0,  (-1.0, 0.0), (0.0, 1.0)),
        ]

        intersection_radius_m = 16.0

        for link_id, name, card, inbound_bearing, forward_vec, right_vec in configs:
            fx, fy = forward_vec  # vector pointing away from center along arm
            rx, ry = right_vec    # vector pointing right of arm

            link = RoadLink(
                link_id=link_id,
                name=name,
                cardinal_direction=card,
                bearing_deg=inbound_bearing,
            )

            # Inbound approach centroid
            app_lat, app_lon = self._offset_gps(
                self.center_lat, self.center_lon,
                fx * (self.arm_len / 2.0), fy * (self.arm_len / 2.0)
            )
            self.approaches[f"{link_id}_inbound"] = IntersectionApproach(
                approach_id=f"{link_id}_inbound",
                name=f"{card}bound Inbound",
                cardinal=card,
                centroid_lat=app_lat,
                centroid_lon=app_lon,
            )

            # Generate Inbound & Outbound lanes
            # Inbound: right side of median
            for idx in range(1, self.num_lanes + 1):
                # Lateral offset for lane
                lat_start = (idx - 1) * self.lane_w + (self.lane_w / 2.0) + 1.0
                lat_left = (idx - 1) * self.lane_w + 1.0
                lat_right = idx * self.lane_w + 1.0

                # Lane 1 = Left / Fast lane (near median), Lane 2 = Right / Slow lane
                # Centerline from outer arm to intersection edge
                p_start_lat, p_start_lon = self._offset_gps(
                    self.center_lat, self.center_lon,
                    fx * self.arm_len + rx * lat_start,
                    fy * self.arm_len + ry * lat_start
                )
                p_end_lat, p_end_lon = self._offset_gps(
                    self.center_lat, self.center_lon,
                    fx * intersection_radius_m + rx * lat_start,
                    fy * intersection_radius_m + ry * lat_start
                )

                # Polygon corners (4 corners)
                c1_lat, c1_lon = self._offset_gps(self.center_lat, self.center_lon, fx * self.arm_len + rx * lat_left, fy * self.arm_len + ry * lat_left)
                c2_lat, c2_lon = self._offset_gps(self.center_lat, self.center_lon, fx * self.arm_len + rx * lat_right, fy * self.arm_len + ry * lat_right)
                c3_lat, c3_lon = self._offset_gps(self.center_lat, self.center_lon, fx * intersection_radius_m + rx * lat_right, fy * intersection_radius_m + ry * lat_right)
                c4_lat, c4_lon = self._offset_gps(self.center_lat, self.center_lon, fx * intersection_radius_m + rx * lat_left, fy * intersection_radius_m + ry * lat_left)

                lane_id = f"{link_id}_inbound_lane_{idx}"
                lane_type = "left_turn" if idx == 1 else "through"

                lane = RoadLane(
                    lane_id=lane_id,
                    link_id=link_id,
                    approach="Inbound",
                    lane_index=idx,
                    lane_type=lane_type,
                    centerline_coords=[[p_start_lon, p_start_lat], [p_end_lon, p_end_lat]],
                    polygon_coords=[
                        [c1_lon, c1_lat],
                        [c2_lon, c2_lat],
                        [c3_lon, c3_lat],
                        [c4_lon, c4_lat],
                        [c1_lon, c1_lat]
                    ],
                    width_meters=self.lane_w,
                    speed_limit_kmh=50.0,
                )
                link.inbound_lanes.append(lane)
                self.lanes[lane_id] = lane

            # Outbound lanes: opposite side of median
            for idx in range(1, self.num_lanes + 1):
                lat_start = -((idx - 1) * self.lane_w + (self.lane_w / 2.0) + 1.0)
                lat_left = -((idx - 1) * self.lane_w + 1.0)
                lat_right = -(idx * self.lane_w + 1.0)

                p_start_lat, p_start_lon = self._offset_gps(
                    self.center_lat, self.center_lon,
                    fx * intersection_radius_m + rx * lat_start,
                    fy * intersection_radius_m + ry * lat_start
                )
                p_end_lat, p_end_lon = self._offset_gps(
                    self.center_lat, self.center_lon,
                    fx * self.arm_len + rx * lat_start,
                    fy * self.arm_len + ry * lat_start
                )

                c1_lat, c1_lon = self._offset_gps(self.center_lat, self.center_lon, fx * intersection_radius_m + rx * lat_left, fy * intersection_radius_m + ry * lat_left)
                c2_lat, c2_lon = self._offset_gps(self.center_lat, self.center_lon, fx * intersection_radius_m + rx * lat_right, fy * intersection_radius_m + ry * lat_right)
                c3_lat, c3_lon = self._offset_gps(self.center_lat, self.center_lon, fx * self.arm_len + rx * lat_right, fy * self.arm_len + ry * lat_right)
                c4_lat, c4_lon = self._offset_gps(self.center_lat, self.center_lon, fx * self.arm_len + rx * lat_left, fy * self.arm_len + ry * lat_left)

                lane_id = f"{link_id}_outbound_lane_{idx}"
                lane = RoadLane(
                    lane_id=lane_id,
                    link_id=link_id,
                    approach="Outbound",
                    lane_index=idx,
                    lane_type="through",
                    centerline_coords=[[p_start_lon, p_start_lat], [p_end_lon, p_end_lat]],
                    polygon_coords=[
                        [c1_lon, c1_lat],
                        [c2_lon, c2_lat],
                        [c3_lon, c3_lat],
                        [c4_lon, c4_lat],
                        [c1_lon, c1_lat]
                    ],
                    width_meters=self.lane_w,
                    speed_limit_kmh=50.0,
                )
                link.outbound_lanes.append(lane)
                self.lanes[lane_id] = lane

            self.links[link_id] = link

    def snap_point_to_network(
        self,
        lat: float,
        lon: float,
        heading_deg: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Bind a single (lat, lon) trajectory coordinate to the nearest link, approach, direction, and lane.

        Returns:
            Dict containing:
                - link_id, link_name, cardinal_direction
                - approach: 'Inbound', 'Outbound', or 'Intersection Core'
                - lane_id, lane_index, lane_type
                - lateral_offset_meters: distance from lane centerline
                - distance_to_intersection_m
        """
        # Distance to intersection center
        lat_rad = math.radians(self.center_lat)
        d_north = (lat - self.center_lat) * (math.pi / 180.0) * self.EARTH_RADIUS
        d_east = (lon - self.center_lon) * (math.pi / 180.0) * (self.EARTH_RADIUS * math.cos(lat_rad))
        dist_to_center = math.sqrt(d_north ** 2 + d_east ** 2)

        if dist_to_center < 16.0:
            return {
                "link_id": "intersection_core",
                "link_name": "Intersection Conflict Area",
                "cardinal_direction": "Intersection Core",
                "approach": "Intersection Core",
                "lane_id": "core_conflict_zone",
                "lane_index": 0,
                "lane_type": "junction_box",
                "lateral_offset_meters": 0.0,
                "distance_to_intersection_m": round(dist_to_center, 1),
            }

        # Find closest lane by point-to-polygon or point-to-centerline distance
        best_lane: Optional[RoadLane] = None
        min_dist = float('inf')

        for lane_id, lane in self.lanes.items():
            # Check point-to-centerline distance
            c_start = lane.centerline_coords[0]
            c_end = lane.centerline_coords[1]

            # Convert to local metric coordinates
            x1 = (c_start[0] - self.center_lon) * (math.pi / 180.0) * (self.EARTH_RADIUS * math.cos(lat_rad))
            y1 = (c_start[1] - self.center_lat) * (math.pi / 180.0) * self.EARTH_RADIUS
            x2 = (c_end[0] - self.center_lon) * (math.pi / 180.0) * (self.EARTH_RADIUS * math.cos(lat_rad))
            y2 = (c_end[1] - self.center_lat) * (math.pi / 180.0) * self.EARTH_RADIUS

            # Distance from point (d_east, d_north) to segment (x1, y1)-(x2, y2)
            seg_len_sq = (x2 - x1)**2 + (y2 - y1)**2
            if seg_len_sq < 1e-4:
                dist = math.sqrt((d_east - x1)**2 + (d_north - y1)**2)
            else:
                t = max(0.0, min(1.0, ((d_east - x1) * (x2 - x1) + (d_north - y1) * (y2 - y1)) / seg_len_sq))
                proj_x = x1 + t * (x2 - x1)
                proj_y = y1 + t * (y2 - y1)
                dist = math.sqrt((d_east - proj_x)**2 + (d_north - proj_y)**2)

            if dist < min_dist:
                min_dist = dist
                best_lane = lane

        if best_lane:
            link = self.links.get(best_lane.link_id)
            link_name = link.name if link else best_lane.link_id
            card = link.cardinal_direction if link else "Unknown"

            # Determine travel direction
            if best_lane.approach == "Inbound":
                direction = f"{card} Approach (Inbound)"
            else:
                direction = f"{card} Exit (Outbound)"

            return {
                "link_id": best_lane.link_id,
                "link_name": link_name,
                "cardinal_direction": card,
                "approach": best_lane.approach,
                "direction": direction,
                "lane_id": best_lane.lane_id,
                "lane_index": best_lane.lane_index,
                "lane_type": best_lane.lane_type,
                "lateral_offset_meters": round(min_dist, 2),
                "distance_to_intersection_m": round(dist_to_center, 1),
            }

        return {
            "link_id": "unknown",
            "link_name": "Off-Network Corridor",
            "cardinal_direction": "Unknown",
            "approach": "Unknown",
            "direction": "Unknown",
            "lane_id": "unknown",
            "lane_index": 0,
            "lane_type": "unknown",
            "lateral_offset_meters": round(min_dist, 2),
            "distance_to_intersection_m": round(dist_to_center, 1),
        }

    def generate_road_network_geojson(self) -> Dict[str, Any]:
        """Generate GeoJSON FeatureCollection of all road links and lane polygons."""
        features = []
        for lane in self.lanes.values():
            features.append(lane.to_geojson_feature())

        return {
            "type": "FeatureCollection",
            "features": features
        }

    def generate_desire_lines_geojson(
        self,
        od_matrix: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate GeoJSON desire lines between origin and destination approaches with volume widths."""
        features = []
        corridors = od_matrix.get("major_corridors", [])

        # Approach cardinal to coordinates map
        app_coords = {
            "North": (self.center_lat + 0.0007, self.center_lon),
            "South": (self.center_lat - 0.0007, self.center_lon),
            "East":  (self.center_lat, self.center_lon + 0.0009),
            "West":  (self.center_lat, self.center_lon - 0.0009),
        }

        for c in corridors:
            orig_name = c.get("origin", "").replace(" Approach", "").strip()
            dest_name = c.get("destination", "").replace(" Approach", "").strip()
            vol = c.get("volume", 0)
            pct = c.get("proportion_pct", 0)

            if orig_name in app_coords and dest_name in app_coords:
                o_lat, o_lon = app_coords[orig_name]
                d_lat, d_lon = app_coords[dest_name]

                # Create curved Bézier path passing through intersection center
                mid_lat = (o_lat + d_lat) / 2.0 * 0.4 + self.center_lat * 0.6
                mid_lon = (o_lon + d_lon) / 2.0 * 0.4 + self.center_lon * 0.6

                # Interpolate 10 points along the desire curve
                curve_pts = []
                for t in np.linspace(0.0, 1.0, 12):
                    b_lat = (1 - t)**2 * o_lat + 2 * (1 - t) * t * mid_lat + t**2 * d_lat
                    b_lon = (1 - t)**2 * o_lon + 2 * (1 - t) * t * mid_lon + t**2 * d_lon
                    curve_pts.append([round(b_lon, 7), round(b_lat, 7)])

                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": curve_pts
                    },
                    "properties": {
                        "origin": orig_name,
                        "destination": dest_name,
                        "volume": vol,
                        "proportion_pct": pct,
                        "stroke_width": max(2, int(vol * 0.4)),
                        "color": "#8b5cf6" if vol > 5 else "#38bdf8",
                    }
                })

        return {
            "type": "FeatureCollection",
            "features": features
        }

    def compute_queue_extents_geojson(
        self,
        tracks: List[Dict[str, Any]],
        queue_speed_thresh_kmh: float = 6.0,
    ) -> Dict[str, Any]:
        """Compute queue extents (LineStrings) along the physical carriageway for queued vehicles."""
        features = []

        # Find queued vehicles by lane
        lane_queued_points: Dict[str, List[Tuple[float, float, float]]] = {}  # lane_id -> [(dist_to_stop, lat, lon)]

        for track in tracks:
            k = track.get("kinematics", {})
            spd = k.get("current_speed_kmh", k.get("average_speed_kmh", 0.0))
            if spd <= queue_speed_thresh_kmh:
                # Queued vehicle
                geo = track.get("geodetic_position", {})
                lat = geo.get("latitude")
                lon = geo.get("longitude")
                lane_id = geo.get("lane_id")

                if lat and lon and lane_id and lane_id in self.lanes:
                    lane = self.lanes[lane_id]
                    if lane.approach == "Inbound":
                        # Distance to stop line
                        dist = geo.get("distance_to_intersection_m", 10.0)
                        if lane_id not in lane_queued_points:
                            lane_queued_points[lane_id] = []
                        lane_queued_points[lane_id].append((dist, lat, lon))

        for lane_id, pts in lane_queued_points.items():
            if len(pts) >= 1:
                lane = self.lanes[lane_id]
                pts_sorted = sorted(pts, key=lambda p: p[0])  # sort from closest to farthest
                max_dist = pts_sorted[-1][0]
                min_dist = pts_sorted[0][0]
                queue_len_m = max(8.0, max_dist - min_dist + 5.0)

                # Draw queue along lane centerline from intersection edge backwards
                c_end = lane.centerline_coords[1]  # intersection edge
                c_start = lane.centerline_coords[0]  # outer arm

                # LineString from stop line to queue tail
                # Interpolate along centerline
                q_coords = [
                    [round(c_end[0], 7), round(c_end[1], 7)],
                    [round(pts_sorted[-1][2], 7), round(pts_sorted[-1][1], 7)]
                ]

                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": q_coords
                    },
                    "properties": {
                        "lane_id": lane_id,
                        "link_id": lane.link_id,
                        "queue_length_meters": round(queue_len_m, 1),
                        "queued_vehicles_count": len(pts),
                        "status": "Active Queue" if len(pts) >= 2 else "Slow Vehicle",
                        "color": "#ef4444" if queue_len_m > 25.0 else "#f59e0b",
                    }
                })

        return {
            "type": "FeatureCollection",
            "features": features
        }

    def compute_per_lane_metrics_geojson(
        self,
        tracks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Aggregate vehicle volume, average speed, and modal split per lane geometry."""
        lane_stats: Dict[str, Dict[str, Any]] = {
            lid: {
                "volume": 0,
                "speeds": [],
                "class_counts": {},
            }
            for lid in self.lanes.keys()
        }

        for track in tracks:
            geo = track.get("geodetic_position", {})
            lid = geo.get("lane_id")
            if lid and lid in lane_stats:
                lane_stats[lid]["volume"] += 1
                k = track.get("kinematics", {})
                spd = k.get("average_speed_kmh", 0.0)
                if spd > 0:
                    lane_stats[lid]["speeds"].append(spd)
                cls = track.get("fine_grained_class", track.get("class_label", "car"))
                lane_stats[lid]["class_counts"][cls] = lane_stats[lid]["class_counts"].get(cls, 0) + 1

        features = []
        for lid, lane in self.lanes.items():
            stats = lane_stats[lid]
            vol = stats["volume"]
            avg_spd = round(float(np.mean(stats["speeds"])), 1) if stats["speeds"] else lane.speed_limit_kmh
            # Modal percentages
            modal_split = {}
            if vol > 0:
                for c_name, count in stats["class_counts"].items():
                    modal_split[c_name] = round((count / vol) * 100.0, 1)

            metrics = {
                "traffic_volume": vol,
                "average_speed_kmh": avg_spd,
                "modal_split_pct": modal_split,
                "lane_status": "Heavy" if vol > 15 else "Moderate" if vol > 5 else "Light",
            }
            features.append(lane.to_geojson_feature(metrics=metrics))

        return {
            "type": "FeatureCollection",
            "features": features
        }
