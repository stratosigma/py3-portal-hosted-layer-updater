# ArcGIS Online/Portal Hosted Layer Updater
This Python 3 script was created for use in automating the update of hosted feature layers in ArcGIS Online or Portal published with ArcGIS Pro. I needed a way to schedule the automated updating of GIS Services as we made changes to the underlying data (parcels, boundaries, roads, etc.) so that they would be reflected in our public viewers on ArcGIS Online with minimal manual interaction.

# Getting Started
The `updateServices.py` file is a Python 3 script that uses source ArcGIS Pro Projects to update hosted feature layers on either ArcGIS Online or ArcGIS Portal (version >= 10.5).
The `settings.config.example` file defines the configuration for the script. See the section below for configuration details. 
Ideally, these two files are used in combination and then added a scheduled task to automate the update of hosted feature layers.

## Prerequisites
* Python 3
* You use ArcGIS Pro 2.2+ or above to publish the hosted feature layer(s). _This script does not work with ArcMap projects_
* The hosted feature layers you want to update must already be published. _This script does not create the initial portal item_
* The `username` in the configuration is assumed to be the owner of the layer(s) you are overwriting
* The `username` you use must be a member of the organization and have publisher or administrator privileges on the portal
* The Portal you use this with must be ArcGIS Online **OR** Portal for ArcGIS version 10.5 or above. _The service overwrite capability in the ArcGIS REST API was not available prior to 10.5_ 

## Disclaimer
Create copies or backups of any hosted feature services you attempt to run this script on. I take no resposibility if this fails to update or corrupts your hosted feature layer(s).

## Running
* Once your configuration is setup, simply running `updateServices.py` will process all services in the configuration file. This file can either be run standalone or as part of a scheduled task.
* The script will create logged output in a file called `services.log` in the same folder as the script.

## Configuration
The script looks for a file called `settings.config` that contains the information needed for authenticating to the portal and information on services to process. The `settings.config.example` shows the general format of this file.

The general format of this file is as follows:

```json
{
    "portal":"The URL of the portal",
    "username":"The username of the account that owns the items",
    "password":"password",
    "retrylimit":1, 
    "services": ["An Array of Service Configurations"]
}
```

The format of a service configuration is as follows:

```json
{
    "name":"The name of the hosted feature layer",
    "id":"When the type is REPLACEVECTORTILE this value is the ItemID of the target layer in ArcGIS Online",
    "project":"The path to the ArcGIS Pro project that contains the map for the hosted feature layer",
    "map":"The name of that map in the ArcGIS Pro project",
    "portalfolder":"The folder on Portal where the hosted layer is published. If it's in your root folder leave blank",
    "type":"This is the type of the hosted layer, it can either be FEATURE, TILE, MAP_IMAGE, or REPLACEVECTORTILE",
    "sharing":{
        "public": "true or false depending on if the layer is public",
        "org": "true or false depending on if the layer is shared with the entire organization",
        "groups":["An array of groups that the layer is shared with"]
    },
    "sync":{
        "frequency":"use one of the following: daily, weekly, monthly, yearly",
        "last":"The date the layer was last processed by this script"
    },
    "tags":"(required for REPLACEVECTORTILE) A comma delimited list of tags for the item",
    "summary":"(required for REPLACEVECTORTILE) A summary of the layer"
}
```
## Authors
* Nick Nolte - Initial Development - City of Grand Island, Nebraska

## License
This project is licensed under the MIT License - see the LICENSE.md file for details

## More Information
* [Updating your hosted feature services with ArcGIS Pro and the ArcGIS API for Python](https://www.esri.com/arcgis-blog/products/api-python/analytics/updating-your-hosted-feature-services-with-arcgis-pro-and-the-arcgis-api-for-python/)
