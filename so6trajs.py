from datetime import datetime
import pandas as pd
import geopandas as gpd
import movingpandas as mpd


def get_gdf(df):
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df.longitude, df.latitude),
        crs={"init": "epsg:4326"},
    )
    return gdf


class So6:
    def __init__(self, file_path):
        columns = [
            "segment_identifier",
            "flight_origin",
            "flight_destination",
            "aircraft_type",
            "time_begin",
            "time_end",
            "fl_begin",
            "fl_end",
            "status",
            "callsign",
            "date_begin",
            "date_end",
            "latitude",
            "longitude",
            "lat_end",
            "lon_end",
            "trajectory_id",
            "sequence",
            "length",
            "parity",
        ]
        parser = lambda x, y: pd.datetime.strptime(x + y, "%y%m%d%H%M%S").replace(
            second=0
        )
        df = pd.read_csv(
            file_path,
            sep=" ",
            header=None,
            names=columns,
            parse_dates={"t": ["date_begin", "time_begin"]},
            date_parser=parser,
        )
        df.query("length > 0", inplace=True)  # filter null segments
        df["altitude"] = df["fl_begin"].apply(lambda x: x * 30.48)  # FL to meters
        lat_lon_cols = ["latitude", "longitude"]
        df[lat_lon_cols] = df[lat_lon_cols].apply(lambda x: x / 60)
        df = df[["t", "trajectory_id", "latitude", "longitude", "altitude"]]
        df.set_index("t", inplace=True)
        df = df[
            df.trajectory_id.duplicated(keep=False)
        ]  # at least two points to form a trajectory
        self.gdf = get_gdf(df)
        self.trajs = []
        for name, group in self.gdf.groupby("trajectory_id"):
            self.trajs.append(mpd.Trajectory(group, name))

    def get_subtrajs(self, polygon, altmin, altmax, starttime, endtime):
        trajs = self.trajs
        trajs = [t for t in trajs if t.get_end_time() > starttime]
        trajs = [t for t in trajs if t.get_start_time() < endtime]
        trajs = [
            t for t in trajs if t.intersects(polygon)
        ]  # intersection but not necessarily during the requested timeframe

        strajs = []
        for t in trajs:
            sdf = t.df.copy()
            trajectory_id = sdf.trajectory_id.iloc[0]
            sdf = sdf[["latitude", "longitude", "altitude"]]
            sdf = sdf.resample("1Min").interpolate("linear")
            sdf = sdf.loc[(sdf.index >= starttime) & (sdf.index <= endtime)]
            alt_min = sdf.altitude.min()
            alt_max = sdf.altitude.max()
            if alt_min <= altmax and altmin <= alt_max:
                sgdf = get_gdf(sdf)
                strajectory = mpd.Trajectory(sgdf, trajectory_id)
                if strajectory.intersects(polygon):
                    strajs.append(strajectory)

        return strajs

    def __repr__(self):
        return f"Size of table: {self.gdf.shape} - Nb of trajs: {len(self.trajs)}"