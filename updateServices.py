import arcpy
import os
import sys
import json
from arcgis.gis import GIS
from datetime import datetime

class Log:
    def __init__(self, msg):
        logfile = os.path.join(sys.path[0],"services.log")
        with open(logfile, 'a') as f:
            datestring = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write("[{}] {}\n".format(datestring, msg))

configFile = os.path.join(sys.path[0],"settings.config")
if not os.path.exists(configFile):
    Log("[FAIL] No configuration file exists. Halting.")
    exit(1)

with open(configFile, 'r') as f:
    config = json.load(f)
    Log("[PASS] Loaded configuration")

portal = config["portal"]
username = config["username"]
password = config["password"]
services = config["services"]
staging = os.path.join(sys.path[0], "staging")
arcpy.env.overwriteOutput = True

Log("[INFO] {} services to update".format(str(len(services))))
Log("[INFO] Staging {}".format(staging))

if not os.path.exists(staging):
    try:
        os.mkdir(staging)
        Log("[INFO] Created a staging folder")
    except:
        Log("[FAIL] Failed to create a staging folder")
        exit(1)

try:
    gis = GIS(portal, username, password)
    Log("[PASS] Connected to Portal")
except:
    Log("[FAIL] Failed to Connect to Portal")
    gis = None

if gis:
    for service in services:
        Log("[INFO] Processing service {}".format(service["name"]))
        service_name = service["name"]
        service_type = service["type"]
        service_folder = service["portalfolder"]
        service_process = service["process"]
        service_sharing = service["sharing"]
        service_map = service["map"]
        service_sddraft = os.path.join(staging, "{}.sddraft".format(service_name))
        service_sd = os.path.join(staging,"{}.sd".format(service_name))
        if service_process:
            try:
                Log("[PASS] Loaded project file for {}".format(service_name))
                project = arcpy.mp.ArcGISProject(service["project"])
            except:
                Log("[FAIL] Failed to load project file for {}".format(service_name))
                project = None

            if project:
                try:
                    mapview = project.listMaps(service_map)[0]
                    Log("[PASS] Retrieved map for {}".format(service_name))
                except:
                    Log("[FAIL] Failed to retrieve map for {}".format(service_name))
                    mapview = None

                if mapview:
                    try:
                        draft = mapview.getWebLayerSharingDraft("HOSTING_SERVER", service_type, service_name)
                        draft.exportToSDDraft(service_sddraft)
                        Log("[PASS] Created Draft Service Definition for {}".format(service_name))
                        try:
                            arcpy.StageService_server(service_sddraft, service_sd)
                            Log("[PASS] Staged Service {}".format(service_name))
                            try:
                                items = gis.content.search("{} AND owner:{}".format(service_name, username), item_type="Service Definition")
                                Log("[INFO] Searching for existing Service Definition")
                                Log("[INFO] Found {} matching Service Definitions".format(str(len(items))))
                                if len(items) == 1:
                                    sditem = items[0]
                                    Log("[PASS] Found existing Service Definition for {} ({})".format(service_name, sditem.id))
                                    try:
                                        Log("[INFO] Attempting to overwrite existing Feature Service Definition for {}".format(service_name))
                                        sditem.update(data=service_sd)
                                        fs = sditem.publish(overwrite=True)
                                        Log("[PASS] Successfully overwrote existing Feature Service Definition for {}".format(service_name))
                                        try:
                                            Log("[INFO] Updating sharing on {}".format(service_name))
                                            fs.share(org=service_sharing["org"], everyone=service_sharing["public"], groups=service_sharing["groups"])
                                            Log("[PASS] Updated sharing on {}".format(service_name))
                                            Log("[PASS] Successfully processed service {}".format(service_name))
                                        except:
                                            Log("[FAIL] Failed to update sharing on {}".format(service_name))                                        
                                    except:
                                        Log("[FAIL] Failed to overwrite existing Feature Service Defintion for {}".format(service_name))
                                else:
                                    Log("[FAIL] Found more than one matching Service Definition for {}".format(service_name))
                            except:
                                Log("[FAIL] Failed to search for existing Service Definition")
                        except:
                            Log("[FAIL] Failed to Stage Service {}".format(service_name))
                    except:
                        Log("[FAIL] Failed to create Draft Service Definition for {}".format(service_name))
                        Log(arcpy.GetMessages())
        else:
            Log("[INFO] Skipped {} - not flagged for processing".format(service_name))
    Log("[INFO] Completed processing services")
Log("[INFO] DONE")