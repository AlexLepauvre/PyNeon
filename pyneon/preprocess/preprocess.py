import pandas as pd
import numpy as np

from typing import TYPE_CHECKING, Union, Literal
from scipy.interpolate import interp1d

from numbers import Number

if TYPE_CHECKING:
    from ..recording import NeonRecording


def _check_data(data: pd.DataFrame, t_col_name: str = "timestamp [ns]") -> None:
    if t_col_name not in data.columns:
        raise ValueError(f"Data must contain a {t_col_name} column")
    if np.any(np.diff(data[t_col_name]) < 0):
        raise ValueError(f"{t_col_name} must be monotonically increasing")


def crop(
    data: pd.DataFrame,
    tmin: Union[Number, None] = None,
    tmax: Union[Number, None] = None,
    by: Literal["timestamp", "time"] = "timestamp",
) -> pd.DataFrame:
    """
    Crop data to a specific time range.

    Parameters
    ----------
    data : pd.DataFrame
        Data to crop. Must contain a monotonically increasing
        ``timestamp [ns]`` or ``time [s]`` column.
    tmin : number, optional
        Start time or timestamp to crop the data to. If ``None``,
        the minimum timestamp or time in the data is used. Defaults to ``None``.
    tmax : number, optional
        End time or timestamp to crop the data to. If ``None``,
        the maximum timestamp or time in the data is used. Defaults to ``None``.
    by : "timestamp" or "time", optional
        Whether tmin and tmax are UTC timestamps in nanoseconds
        or relative times in seconds. Defaults to "timestamp".

    Returns
    -------
    pd.DataFrame
        Cropped data.
    """
    if tmin is None and tmax is None:
        raise ValueError("At least one of tmin or tmax must be provided")
    t_col_name = "timestamp [ns]" if by == "timestamp" else "time [s]"
    _check_data(data, t_col_name=t_col_name)
    tmin = tmin if tmin is not None else data[t_col_name].min()
    tmax = tmax if tmax is not None else data[t_col_name].max()
    return data[(data[t_col_name] >= tmin) & (data[t_col_name] <= tmax)]


def interpolate(
    new_ts: np.ndarray,
    data: pd.DataFrame,
    float_kind: str = "linear",
    other_kind: str = "nearest",
) -> pd.DataFrame:
    """
    Interpolate a data stream to a new set of timestamps.

    Parameters
    ----------
    new_ts : np.ndarray, optional
        New timestamps to evaluate the interpolant at.
    data : pd.DataFrame
        Data to interpolate. Must contain a monotonically increasing
        ``timestamp [ns]`` column.
    float_kind : str, optional
        Kind of interpolation applied on columns of float type,
        by default "linear". For details see :class:`scipy.interpolate.interp1d`.
    other_kind : str, optional
        Kind of interpolation applied on columns of other types,
        by default "nearest".

    Returns
    -------
    pandas.DataFrame
        Interpolated data.
    """
    _check_data(data)
    new_ts = np.sort(new_ts)
    new_data = pd.DataFrame(data=new_ts, columns=["timestamp [ns]"], dtype="Int64")
    new_data["time [s]"] = (new_ts - new_ts[0]) / 1e9
    for col in data.columns:
        # Skip time columns
        if col == "timestamp [ns]" or col == "time [s]":
            continue
        # Float columns are interpolated with float_kind
        if pd.api.types.is_float_dtype(data[col]):
            new_data[col] = interp1d(
                data["timestamp [ns]"],
                data[col],
                kind=float_kind,
                bounds_error=False,
            )(new_ts)
        # Other columns are interpolated with other_kind
        else:
            new_data[col] = interp1d(
                data["timestamp [ns]"],
                data[col],
                kind=other_kind,
                bounds_error=False,
            )(new_ts)
        # Ensure the new column has the same dtype as the original
        new_data[col] = new_data[col].astype(data[col].dtype)
    return new_data


def window_average(
    new_ts: np.ndarray,
    data: pd.DataFrame,
    window_size: Union[int, None] = None,
) -> pd.DataFrame:
    """
    Take the average over a time window to obtain smoothed data at new timestamps.

    Parameters
    ----------
    new_ts : np.ndarray
        New timestamps to evaluate the window average at. The median of the differences
        between the new timestamps must be larger than the median of the differences
        between the old timestamps. In other words, only downsampling is supported.
    data : pd.DataFrame
        Data to apply window average to. Must contain a monotonically increasing
        ``timestamp [ns]`` column.
    window_size : int, optional
        Size of the time window in nanoseconds. If ``None``, the window size is
        set to the median of the differences between the new timestamps.
        Defaults to ``None``.

    Returns
    -------
    pd.DataFrame
        Data with window average applied.
    """
    _check_data(data)
    new_ts = np.sort(new_ts)
    new_ts_median_diff = np.median(np.diff(new_ts))
    # Assert that the new_ts has a lower sampling frequency than the old data
    if new_ts_median_diff < np.mean(np.diff(data["timestamp [ns]"])):
        raise ValueError(
            "new_ts must have a lower sampling frequency than the old data"
        )
    if window_size is None:
        window_size = int(new_ts_median_diff)
    new_data = pd.DataFrame(data=new_ts, columns=["timestamp [ns]"], dtype="Int64")
    new_data["time [s]"] = (new_ts - new_ts[0]) / 1e9
    for col in data.columns:
        # Skip time columns
        if col == "timestamp [ns]" or col == "time [s]":
            continue
        new_values = []  # List to store the downsampled values
        for ts in new_ts:
            # Define the time window around the current new timestamp
            lower_bound = ts - window_size / 2
            upper_bound = ts + window_size / 2
            # Select rows from old_data that fall within the time window
            window_data = data[
                (data["timestamp [ns]"] >= lower_bound)
                & (data["timestamp [ns]"] <= upper_bound)
            ]
            # Append data within this window
            if not window_data.empty:
                new_values.append(window_data[col].mean())
            else:
                new_values.append(np.nan)
        # Assign the downsampled values to the new DataFrame
        new_data[col] = new_values

    return new_data


_VALID_STREAMS = {"3d_eye_states", "eye_states", "gaze", "imu"}


def concat_streams(
    rec: "NeonRecording",
    stream_names: Union[str, list[str]] = "all",
    sampling_freq: Union[Number, str] = "min",
    interp_float_kind: str = "linear",
    interp_other_kind: str = "nearest",
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Concatenate data from different streams under common timestamps.
    Since the streams may have different timestamps and sampling frequencies,
    interpolation of all streams to a set of common timestamps is performed.
    The latest start timestamp and earliest last timestamp of the selected streams
    are used to define the common timestamps.

    Parameters
    ----------
    rec : :class:`NeonRecording`
        NeonRecording object containing the streams to concatenate.
    stream_names : str or list of str
        Stream names to concatenate. If "all", then all streams will be used.
        If a list, items must be in ``{"gaze", "imu", "eye_states"}``
        (``"3d_eye_states"``) is also tolerated as an alias for ``"eye_states"``).
    sampling_freq : float or int or str, optional
        Sampling frequency of the concatenated streams.
        If numeric, the streams will be interpolated to this frequency.
        If ``"min"``, the lowest nominal sampling frequency
        of the selected streams will be used.
        If ``"max"``, the highest nominal sampling frequency will be used.
        Defaults to ``"min"``.
    interp_float_kind : str, optional
        Kind of interpolation applied on columns of float type,
        Defaults to ``"linear"``. For details see :class:`scipy.interpolate.interp1d`.
    interp_other_kind : str, optional
        Kind of interpolation applied on columns of other types.
        Defaults to ``"nearest"``.
    inplace : bool, optional
        Replace selected stream data with interpolated data during concatenation
        if``True``. Defaults to ``False``.

    Returns
    -------
    concat_data : :class:`pandas.DataFrame`
        Concatenated data.
    """
    if isinstance(stream_names, str):
        if stream_names == "all":
            stream_names = list(_VALID_STREAMS)
        else:
            raise ValueError(
                "Invalid stream_names, must be 'all' or a list of stream names."
            )
    if len(stream_names) <= 1:
        raise ValueError("Must provide at least two streams to concatenate.")

    stream_names = [ch.lower() for ch in stream_names]
    # Check if all streams are valid
    if not all([ch in _VALID_STREAMS for ch in stream_names]):
        raise ValueError(f"Invalid stream name, can only one of {_VALID_STREAMS}")

    stream_info = pd.DataFrame(columns=["stream", "name", "sf", "first_ts", "last_ts"])
    print("Concatenating streams:")
    if "gaze" in stream_names:
        if rec.gaze is None:
            raise ValueError("Cannnot load gaze data.")
        stream_info = pd.concat(
            [
                stream_info,
                pd.Series(
                    {
                        "stream": rec.gaze,
                        "name": "gaze",
                        "sf": rec.gaze.sampling_freq_nominal,
                        "first_ts": rec.gaze.first_ts,
                        "last_ts": rec.gaze.last_ts,
                    }
                )
                .to_frame()
                .T,
            ],
            ignore_index=True,
        )
        print("\tGaze")
    if "3d_eye_states" in stream_names or "eye_states" in stream_names:
        if rec.eye_states is None:
            raise ValueError("Cannnot load eye states data.")
        stream_info = pd.concat(
            [
                stream_info,
                pd.Series(
                    {
                        "stream": rec.eye_states,
                        "name": "3d_eye_states",
                        "sf": rec.eye_states.sampling_freq_nominal,
                        "first_ts": rec.eye_states.first_ts,
                        "last_ts": rec.eye_states.last_ts,
                    }
                )
                .to_frame()
                .T,
            ],
            ignore_index=True,
        )
        print("\t3D eye states")
    if "imu" in stream_names:
        if rec.imu is None:
            raise ValueError("Cannnot load IMU data.")
        stream_info = pd.concat(
            [
                stream_info,
                pd.Series(
                    {
                        "stream": rec.imu,
                        "name": "imu",
                        "sf": rec.imu.sampling_freq_nominal,
                        "first_ts": rec.imu.first_ts,
                        "last_ts": rec.imu.last_ts,
                    }
                )
                .to_frame()
                .T,
            ],
            ignore_index=True,
        )
        print("\tIMU")

    # Lowest sampling rate
    if sampling_freq == "min":
        sf = stream_info["sf"].min()
        sf_type = "lowest"
    elif sampling_freq == "max":
        sf = stream_info["sf"].max()
        sf_type = "highest"
    elif isinstance(sampling_freq, (int, float)):
        sf = sampling_freq
        sf_type = "customized"
    else:
        raise ValueError("Invalid sampling_freq, must be 'min', 'max', or numeric")
    sf_name = stream_info.loc[stream_info["sf"] == sf, "name"].values
    print(f"Using {sf_type} sampling rate: {sf} Hz ({sf_name})")

    max_first_ts = stream_info["first_ts"].max()
    max_first_ts_name = stream_info.loc[
        stream_info["first_ts"] == max_first_ts, "name"
    ].values
    print(f"Using latest start timestamp: {max_first_ts} ({max_first_ts_name})")

    min_last_ts = stream_info["last_ts"].min()
    min_last_ts_name = stream_info.loc[
        stream_info["last_ts"] == min_last_ts, "name"
    ].values
    print(f"Using earliest last timestamp: {min_last_ts} ({min_last_ts_name})")

    new_ts = np.arange(
        max_first_ts,
        min_last_ts,
        int(1e9 / sf),
        dtype=np.int64,
    )

    concat_data = pd.DataFrame(data=new_ts, columns=["timestamp [ns]"], dtype="Int64")
    concat_data["time [s]"] = (new_ts - new_ts[0]) / 1e9
    for stream in stream_info["stream"]:
        resamp_df = stream.interpolate(
            new_ts, interp_float_kind, interp_other_kind, inplace=inplace
        )
        assert concat_data.shape[0] == resamp_df.shape[0]
        assert concat_data["timestamp [ns]"].equals(resamp_df["timestamp [ns]"])
        concat_data = pd.merge(
            concat_data, resamp_df, on=["timestamp [ns]", "time [s]"], how="inner"
        )
        assert concat_data.shape[0] == resamp_df.shape[0]
    return concat_data


VALID_EVENTS = {
    "blink",
    "blinks",
    "fixation",
    "fixations",
    "saccade",
    "saccades",
    "event",
    "events",
}


def concat_events(
    rec: "NeonRecording",
    event_names: Union[str, list[str]],
) -> pd.DataFrame:
    """
    Concatenate different events. All columns in the selected event type will be
    present in the final DataFrame. An additional ``type`` column denotes the event
    type. If ``"events"`` is in ``event_names``, its ``timestamp [ns]`` column will be
    renamed to ``start timestamp [ns]``, and the ``name`` and ``type`` columns will
    be renamed to ``message name`` and ``message type`` respectively to provide
    a more readable output.

    Parameters
    ----------
    rec : :class:`NeonRecording`
        NeonRecording object containing the events to concatenate.
    event_names : list of str
        List of event names to concatenate. Event names must be in
        ``{"blinks", "fixations", "saccades", "events"}``
        (singular forms are tolerated).

    Returns
    -------
    concat_events : :class:`pandas.DataFrame`
        Concatenated events.
    """
    if isinstance(event_names, str):
        if event_names == "all":
            event_names = list(VALID_EVENTS)
        else:
            raise ValueError(
                "Invalid event_names, must be 'all' or a list of event names."
            )

    if len(event_names) <= 1:
        raise ValueError("Must provide at least two events to concatenate.")

    event_names = [ev.lower() for ev in event_names]
    # Check if all events are valid
    if not all([ev in VALID_EVENTS for ev in event_names]):
        raise ValueError(f"Invalid event name, can only be {VALID_EVENTS}")

    concat_data = pd.DataFrame(
        {
            "type": pd.Series(dtype="str"),
            "start timestamp [ns]": pd.Series(dtype="Int64"),
            "end timestamp [ns]": pd.Series(dtype="Int64"),
            "duration [ms]": pd.Series(dtype="float64"),
        }
    )
    print("Concatenating events:")
    if "blinks" in event_names or "blink" in event_names:
        if rec.blinks is None:
            raise ValueError("Cannnot load blink data.")
        data = rec.blinks.data
        data["type"] = "blink"
        concat_data = pd.concat([concat_data, data], ignore_index=True)
        print("\tBlinks")
    if "fixations" in event_names or "fixation" in event_names:
        if rec.fixations is None:
            raise ValueError("Cannnot load fixation data.")
        data = rec.fixations.data
        data["type"] = "fixation"
        concat_data = pd.concat([concat_data, data], ignore_index=True)
        print("\tFixations")
    if "saccades" in event_names or "saccade" in event_names:
        if rec.saccades is None:
            raise ValueError("Cannnot load saccade data.")
        data = rec.saccades.data
        data["type"] = "saccade"
        concat_data = pd.concat([concat_data, data], ignore_index=True)
        print("\tSaccades")
    if "events" in event_names or "event" in event_names:
        if rec.events is None:
            raise ValueError("Cannnot load event data.")
        data = rec.events.data
        data.rename(
            columns={"name": "message name", "type": "message type"}, inplace=True
        )
        data["type"] = "event"
        data.rename(columns={"timestamp [ns]": "start timestamp [ns]"}, inplace=True)
        concat_data = pd.concat([concat_data, data], ignore_index=True)
        print("\tEvents")
    concat_data.sort_values("start timestamp [ns]", inplace=True)
    concat_data.reset_index(drop=True, inplace=True)
    return concat_data
