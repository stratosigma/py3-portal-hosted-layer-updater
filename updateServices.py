import arcpy
import os
import sys
import json
from arcgis.gis import GIS
from datetime import datetime
from dateutil import relativedelta

class Log:
    def __init__(self, msg):
        logfile = os.path.join(sys.path[0],"services.log")
        with open(logfile, 'a') as f:
            datestring = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write("[{}] {}\n".format(datestring, msg))

def getSync(syncobj):
    freq = {
        "frequency":"never",
        "last":"1999-01-01"
    }
    if "frequency" in syncobj and "last" in syncobj:
        f = syncobj["frequency"]
        l = syncobj["last"]
        lo = None
        freq["last"] = datetime.strptime(l, "%Y-%m-%d")
        if f == "daily":
            freq["frequency"] = relativedelta.relativedelta(days=-1)
        if f == "weekly":
            freq["frequency"] = relativedelta.relativedelta(weeks=-1)
        if f == "monthly":
            freq["frequency"] = relativedelta.relativedelta(months=-1)
        if f == "yearly":
            freq["frequency"] = relativedelta.relativedelta(years=-1)
    return freq
        

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
retrylimit = config["retrylimit"] if config["retrylimit"] > 0 else 1
staging = os.path.join(sys.path[0], "staging")
arcpy.env.overwriteOutput = True

Log("[INFO] {} services to update".format(str(len(services))))
Log("[INFO] Retry limit set to {}".format(str(retrylimit)))
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
        service_update = getSync(service["sync"])
        service_sddraft = os.path.join(staging, "{}.sddraft".format(service_name))
        service_sd = os.path.join(staging,"{}.sd".format(service_name))
        if service_update["last"] <= (datetime.now() + service_update["frequency"]):
            if service_process:
                try:
                    Log("[PASS] Loaded project file for {}".format(service_name))
                    project = arcpy.mp.ArcGISProject(service["project"])
                except:
                    Log("[FAIL] Failed to load project file for {}".format(service_name))
                    project = None

                if service_type in ["FEATURE", "REPLACEVECTORTILE"]:
                    if project:
                        try:
                            mapview = project.listMaps(service_map)[0]
                            Log("[PASS] Retrieved map for {}".format(service_name))
                        except:
                            Log("[FAIL] Failed to retrieve map for {}".format(service_name))
                            mapview = None

                        if mapview:
                            if service_type == "FEATURE":
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
                                                attempts = 0
                                                while True:
                                                    try:
                                                        attempts += 1
                                                        Log("[INFO] Attempting to overwrite existing Feature Service Definition for {}".format(service_name))
                                                        sditem.update(data=service_sd)
                                                        fs = sditem.publish(overwrite=True)
                                                        Log("[PASS] Successfully overwrote existing Feature Service Definition for {}".format(service_name))
                                                        try:
                                                            Log("[INFO] Updating sharing on {}".format(service_name))
                                                            fs.share(org=service_sharing["org"], everyone=service_sharing["public"], groups=service_sharing["groups"])
                                                            Log("[PASS] Updated sharing on {}".format(service_name))
                                                            Log("[PASS] Successfully processed service {}".format(service_name))
                                                            service["sync"]["last"] = datetime.now().strftime("%Y-%m-%d")
                                                        except:
                                                            Log("[FAIL] Failed to update sharing on {}".format(service_name))                                        
                                                    except Exception as e:
                                                        Log("[FAIL] Failed to overwrite existing Feature Service Defintion for {} [Attempts: {}]".format(service_name, str(attempts)))
                                                        if attempts < retrylimit:
                                                            Log(e)
                                                    break
                                            else:
                                                Log("[FAIL] Found more than one matching Service Definition for {}".format(service_name))
                                        except:
                                            Log("[FAIL] Failed to search for existing Service Definition")
                                    except:
                                        Log("[FAIL] Failed to Stage Service {}".format(service_name))
                                except Exception as e:
                                    Log("[FAIL] Failed to create Draft Service Definition for {}".format(service_name))
                                    Log(arcpy.GetMessages())
                                    Log(e)
                            elif service_type == "REPLACEVECTORTILE":
                                service_summary = service["summary"]
                                service_tags = service["tags"]
                                service_id = service["id"]
                                service_public = "EVERYBODY" if service_sharing["public"] == True else "MYGROUPS"

                                vtpk_name = "{}_{}".format(service_name, datetime.strftime(datetime.now(),'%Y%m%d_%H%M%S'))
                                vtpk_path = os.path.join(staging, "{}.vtpk".format(vtpk_name))
                                try:
                                    arcpy.management.CreateVectorTilePackage(mapview, vtpk_path, "ONLINE", "", "INDEXED", 577790.554288, 282.124294)
                                    Log("[PASS] Generated Vector Tile Package {} for {}".format(vtpk_path, service_name))
                                    Log("[INFO] Attempting to publish Vector Tile Package")
                                    try:
                                        publish = arcpy.management.SharePackage(vtpk_path, username, password, service_summary, service_tags, public=service_public, groups=service_sharing["groups"], publish_web_layer="TRUE", portal_folder=service_folder)
                                        Log("[PASS] Successfully published Vector Tile Package. ItemID {}".format(publish[2]))
                                        Log("[INFO] Attempting to replace Vector Tiles for {} with {}".format(service_name, vtpk_name))
                                        publish_result = json.loads(publish[1])
                                        try:
                                            replaced = gis.content.replace_service(service_id, publish_result["publishResult"]["serviceItemId"], replace_metadata=False)
                                            Log("[PASS] Successfully replaced Vector Tile Service {} with {}".format(service_name, vtpk_name))
                                            service["sync"]["last"] = datetime.now().strftime("%Y-%m-%d")
                                            try:
                                                arcpy.management.Delete(vtpk_path)
                                                Log("[PASS] Deleted staging tile package")
                                            except:
                                                Log("[FAIL] Failed to delete staging tile package, {}".format(vtpk_path))
                                                Log(arcpy.GetMessages())
                                        except Exception as e:
                                            Log("[FAIL] Failed to replace Vector Tile Service {} with {}".format(service_name, vtpk_name))
                                            Log(arcpy.GetMessages())
                                            Log(e)
                                    except:
                                        Log("[FAIL] Failed to publish Vector Tile Package")
                                        Log(arcpy.GetMessages())
                                except:
                                    Log("[FAIL] Failed to generate Vector Tile Package for {}".format(service_name))
                                    Log(arcpy.GetMessages())
            else:
                Log("[INFO] Skipped {} - not flagged for processing".format(service_name))
        else:
            Log("[SKIP] Skipped {} because not time to update yet".format(service_name))
    Log("[INFO] Completed processing services")
Log("[INFO] Writing File")
with open(configFile, 'w') as f:
    json.dump(config, f, indent=4, separators=(',',':'), sort_keys=True)
Log("[INFO] DONE")
