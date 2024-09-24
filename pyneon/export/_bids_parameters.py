MOTION_META_DEFAULT = {
    "TaskName": "",
    "TaskDescription": "",
    "Instructions": "",
    "DeviceSerialNumber": "",
    "Manufacturer": "TDK InvenSense & Pupil Labs",
    "ManufacturersModelName": "ICM-20948",
    "SoftwareVersions": "",
    "InstitutionName": "",
    "InstitutionAddress": "",
    "InstitutionalDepartmentName": "",
    "SamplingFrequency": "",
    "ACCELChannelCount": 3,
    "GYROChannelCount": 3,
    "MissingValues": "n/a",
    "MotionChannelCount": 13,
    "ORNTChannelCount": 7,
    "SubjectArtefactDescription": "",
    "TrackedPointsCount": 0,
    "TrackingSystemName": "IMU included in Neon",
}

EYE_META_DEFAULT = {
    "SamplingFrequency": "",
    "StartTime": 0,
    "Columns": [
        "timestamp",
        "x_coordinate",
        "y_coordinate",
        "azimuth",
        "elevation",
        "pupil_size_left",
        "pupil_size_right",
    ],
    "DeviceSerialNumber": "",
    "Manufacturer": "Pupil Labs",
    "ManufacturersModelName": "Neon",
    "SoftwareVersions": "",
    "PhysioType": "eyetrack",
    "EnvironmentCoorinates": "top-left",
    "RecordedEye": "cyclopean",
    "SampleCoordinateUnits": "pixels",
    "SampleCoordinateSystem": "gaze-in-world",
    "EyeTrackingMethod": "real-time neural network",
    "azimuth": {
        "Description": "Azimuth of the gaze ray in relation to the scene camera",
        "Units": "degrees",
    },
    "elevation": {
        "Description": "Elevation of the gaze ray in relation to the scene camera",
        "Units": "degrees",
    },
    "pupil_size_left": {
        "Description": "Physical diameter of the pupil of the left eye",
        "Units": "mm",
    },
    "pupil_size_right": {
        "Description": "Physical diameter of the pupil of the right eye",
        "Units": "mm",
    },
}
