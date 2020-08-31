# airq-data

This repository is used to build the [Purpleair](https://www2.purpleair.com/) data for the [airq app](https://github.com/airq-dev/airq#airq). Purpleair collects data from thousands of sensors around the world, each with a latitude and longitude; we:
* Pull this data down from their API;
* Calculate the geohash of each sensor;
* Write an entry in a sqlite3 database.

We also build a table containing data about zipcodes, using public data from Geonames. We store the geohash of each zipcode, allowing us to perform a reverse lookup when a user inputs a zipcode: we determine its geohash and then determine the nearby sensors. Then we make an API call to Purpleair to determine the average air quality.

This repository runs a cron once per day to rebuild the database described above and push it to the airq repository. It will then be auto-merged if tests pass, triggering a new deploy.
