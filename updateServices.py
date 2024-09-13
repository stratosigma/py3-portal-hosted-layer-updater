import arcpy
import os
import sys
import json
from time import sleep
from arcgis.gis import GIS
from datetime import datetime
from dateutil import relativedelta

class Log:
    def __init__(self, msg):
        logfile = os.path.join(sys.path[0],"services.log")
        with open(logfile, 'a') as f:
            datestring = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write("[{}] {}\n".format(datestring, msg))

def encode(key, string):
    encoded_chars = []
    for i in range(len(string)):
        key_c = key[i % len(key)]
        encoded_c = chr(ord(string[i]) + ord(key_c) % 256)
        encoded_chars.append(encoded_c)
    encoded_string = "".join(encoded_chars)
    return encoded_string

def decode(key, string):
    encoded_chars = []
    for i in range(len(string)):
        key_c = key[i % len(key)]
        encoded_c = chr(ord(string[i]) - ord(key_c) % 256)
        encoded_chars.append(encoded_c)
    encoded_string = "".join(encoded_chars)
    return encoded_string

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
tasks = config["tasks"] if "tasks" in config else None
encrypted = config["encrypted"] if "encrypted" in config else None

if not encrypted:    
    password = encode("shenannigans", password)
    config["password"] = password
    config["encrypted"] = True

password = decode("shenannigans", password)
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
        service_update = getSync(service["sync"])
        service_sddraft = os.path.join(staging, "{}.sddraft".format(service_name))
        service_sd = os.path.join(staging,"{}.sd".format(service_name))
        if service_update["last"] <= (datetime.now() + service_update["frequency"]):
            if service_process:
                if service_type in ["FEATURE", "REPLACEVECTORTILE", "REPLACETILE"]:
                    service_map = service["map"]
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
                            elif service_type in ["REPLACEVECTORTILE", "REPLACETILE"]:
                                service_summary = service["summary"]
                                service_tags = service["tags"]
                                service_id = service["id"]
                                service_sharing = service["sharing"]
                                service_public = "EVERYBODY" if service_sharing["public"] == True else "MYGROUPS"

                                pk_name = "{}_{}".format(service_name, datetime.strftime(datetime.now(),'%Y%m%d_%H%M%S'))
                                pk_path = os.path.join(staging, "{}.{}".format(pk_name, "vtpk" if service_type == "REPLACEVECTORTILE" else "tpkx"))
                                mapview.clearSelection()
                                try:
                                    if service_type == "REPLACEVECTORTILE":
                                        arcpy.management.CreateVectorTilePackage(mapview, pk_path, "ONLINE", "", "INDEXED", 577790.554288, 282.124294)
                                        Log("[PASS] Generated Vector Tile Package {} for {}".format(pk_path, service_name))
                                        Log("[INFO] Attempting to publish Vector Tile Package")
                                    elif service_type == "REPLACETILE":
                                        aoi_layer = None
                                        aoi_selectors = None
                                        aoi_selector_layers = []
                                        if "parameters" in service:
                                            aoi_layer = service["parameters"]["aoi"] if "aoi" in service["parameters"] else None
                                            aoi_selectors = service["parameters"]["aoi_selectors"] if "aoi_selectors" in service["parameters"] else None
                                            aoil = mapview.listLayers(aoi_layer)
                                            if len(aoil) == 1:
                                                aoi_layer = aoil[0]
                                            else:
                                                Log("[INFO] Failed to find AOI Layer: {}".format(aoi_layer))
                                                aoi_layer = None

                                            for aoi_selector in aoi_selectors:                                                
                                                aois = mapview.listLayers(aoi_selector)
                                                if len(aois) == 1:
                                                    aoi_selector_layers.append(aois[0])
                                                else:
                                                    Log("[INFO] Failed to find AOI Selector: {}".format(aoi_selector))

                                        if aoi_selector_layers:
                                            for i, aoi_selector_layer in enumerate(aoi_selector_layers):
                                                try:
                                                    arcpy.management.SelectLayerByLocation(aoi_layer, "INTERSECT", aoi_selector_layer,selection_type=("NEW_SELECTION" if i == 0 else "ADD_TO_SELECTION"))
                                                    Log("[INFO] Selecting AOI that intersects {}".format(aoi_selector_layers[i].name))
                                                except:
                                                    Log("[FAIL] Failed to select AOI that intersects {}".format(aoi_selector_layers[i]))
                                                    Log(arcpy.GetMessages())

                                        Log("[INFO] Beginning Tile Package Generation for {} in {}".format(service_map, project.filePath))
                                        try:
                                            arcpy.management.CreateMapTilePackage(mapview, "ONLINE", pk_path, "PNG8", 21, None, '', '', aoi_layer.name, 75, 'tpkx', 19, aoi_layer)
                                            Log("[PASS] Tile package generated successfully")
                                        except:
                                            Log("[FAIL] Failed to generate tile package for {} in {}".format(service_map, project.filePath))
                                            Log(arcpy.GetMessages())                                        
                                            
                                    try:
                                        publish = arcpy.management.SharePackage(pk_path, username, password, service_summary, service_tags, public=service_public, groups=service_sharing["groups"], publish_web_layer="TRUE", portal_folder=service_folder)
                                        Log("[PASS] Successfully published {} Package. ItemID {}".format("Vector Tile" if service_type == "REPLACEVECTORTILE" else "Tile", publish[2]))
                                        Log("[INFO] Attempting to replace Tiles for {} with {}".format(service_name, pk_name))
                                        publish_result = json.loads(publish[1])
                                        sleep(10)
                                        try:
                                            replaced = gis.content.replace_service(service_id, publish_result["publishResult"]["serviceItemId"], replace_metadata=False)
                                            Log("[PASS] Successfully replaced {} Service {} with {}".format("Vector Tile" if service_type == "REPLACEVECTORTILE" else "Tile", service_name, pk_name))
                                            service["sync"]["last"] = datetime.now().strftime("%Y-%m-%d")
                                            try:
                                                arcpy.management.Delete(pk_path)
                                                Log("[PASS] Deleted staging tile package")
                                            except:
                                                Log("[FAIL] Failed to delete staging tile package, {}".format(pk_path))
                                                Log(arcpy.GetMessages())
                                        except Exception as e:
                                            Log("[FAIL] Failed to replace Tile Service {} with {}".format(service_name, pk_name))
                                            Log(arcpy.GetMessages())
                                            Log(e)
                                    except:
                                        Log("[FAIL] Failed to publish Tile Package")
                                        Log(arcpy.GetMessages())
                                except:
                                    Log("[FAIL] Failed to generate Tile Package for {}".format(service_name))
                                    Log(arcpy.GetMessages())
                            else:
                                Log("[FAIL] Service Type, {}, not implemented".format(service_type))
                        else:
                            Log("[FAIL] Failed to retrieve map for {}".format(service_name))
                    else:
                        Log("[FAIL] Failed to load project file for {}".format(service_name))
                else:
                    Log("[FAIL] Service Type, {}, not implemented".format(service_type))                
            else:
                Log("[INFO] Skipped {} - not flagged for processing".format(service_name))
        else:
            Log("[SKIP] Skipped {} because not time to update yet".format(service_name))
    for task in tasks:
        if task['type'] in ['CLEAN']:
            search_string = task['find'] if 'find' in task else None
            older_than = task['olderthan'] if 'olderthan' in task else 7
            owner = task['owner'] if 'owner' in task else None
            process = task['process'] if 'process' in task else False
            update = getSync(task['sync']) if 'sync' in task else None
            summary = task['summary']
            content_type = task['content_type'] if 'content_type' in task else None
            folder = task['folder'] if 'folder' in task else None

            if search_string and update:
                if update["last"] <= (datetime.now() + update["frequency"]):
                    try:
                        if owner and content_type:
                            results = gis.content.search(query="title:{} type:{} owner:{}".format(search_string, content_type, owner), max_items=-1) 
                        elif owner and not content_type:
                            results = gis.content.search(query="title:{} owner:{}".format(search_string, owner), max_items=-1) 
                        elif content_type and not owner:
                            results = gis.content.search(query="title:{} type:{}".format(search_string, content_type), max_items=-1)
                        else:
                            results = gis.content.search(query="title:{}".format(search_string), max_items=-1)                         

                        Log("[INFO] Found {} items that match the query {}".format(str(len(results)),search_string))
                        if len(results) > 0:
                            checkpoint = datetime.now() - relativedelta.relativedelta(days=older_than)
                            for result in results:
                                if result.title.startswith(search_string):
                                    modified_date = datetime.fromtimestamp(result.modified/1000)
                                    created_date = datetime.fromtimestamp(result.created/1000)
                                    if modified_date < checkpoint and created_date < checkpoint:
                                        Log("[INFO] {} is older than {} days, attempting to delete".format(result.title, str(older_than)))
                                        if not result.can_delete:
                                            Log("[INFO] {} is delete protected".format(result.title))
                                        else:
                                            Log("[INFO] DELETE {}".format(result.title))
                                            deleted = result.delete(dry_run=True)
                                            if deleted['can_delete']:
                                                try:
                                                    result.delete()
                                                    Log("[PASS] DELETED {} successfully".format(result.title))
                                                except Exception as e:
                                                    Log("[FAIL] Failed to Delete {}".format(result.title))
                                                    Log(e)
                                    else:
                                        Log("[INFO] {} is not older than {}, keeping".format(result.title, str(older_than)))
                                else:
                                    Log("[INFO] {} does not begin with {}, skipping".format(result.title, search_string))
                            task["sync"]["last"] = datetime.now().strftime("%Y-%m-%d")
                        else:
                            Log("[INFO] No results found for query {}".format(search_string))
                    except:
                        Log("[FAIL] Failed to search for {}".format(search_string))
                else:
                    Log("[INFO] Skipping, {}, because not time to run yet".format(summary))
                
            else:
                if not search_string:
                    Log("[FAIL] No search string specified in find for {}".format(summary))
                if not update:
                    Log("[FAIL] No update frequency set for {}".format(summary))

    Log("[INFO] Completed processing services")
Log("[INFO] Writing File")
with open(configFile, 'w') as f:
    json.dump(config, f, indent=4, separators=(',',':'), sort_keys=True)
Log("[INFO] DONE")
