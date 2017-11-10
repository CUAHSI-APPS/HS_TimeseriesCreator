from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import ensure_csrf_cookie
from tethys_apps.base import TethysWorkspace
import traceback
import json
import shutil
import os
import time
from .utilities import get_user_workspace, create_ts_resource, create_refts_resource, get_o_auth_hs


@csrf_exempt
def login_test(request):
    """
    Ajax controller for login_test. Tests user login.

    Arguments:      [request]
    Returns:        [JsonRespoTethysWorkspacense({'Login': login_status})]
    Referenced By:  []
    References:     []
    Libraries:      []
    """

    return_obj = {
        'success': "False",
        'message': None,
        'results': {}
    }

    if request.user.is_authenticated():
        data_url = request.POST.get('dataUrl')
        hs = get_o_auth_hs(request)
        hs_version = hs.hostname
        if "appsdev.hydroshare.org" in str(data_url) and "beta" in str(hs_version):
            return_obj['success'] = "True"
        elif "apps.hydroshare.org" in str(data_url) and "www" in str(hs_version):
            return_obj['success'] = "True"
        elif "127.0.0.1:8000" in str(data_url) and "beta" in str(hs_version):
            return_obj['success'] = "True"
        else:
            return_obj['success'] = "False"
    else:
        return_obj['success'] = "False"

    return JsonResponse(return_obj)


@csrf_exempt
def ajax_create_resource(request):
    """
    Ajax controller for create_layer.

    Arguments:      []
    Returns:        []
    Referenced By:  []
    References:     []
    Libraries:      []
    """

    return_obj = {
        "success": False,
        "message": None,
        "results": {}
    }

    # -------------------- #
    #   VERIFIES REQUEST   #
    # -------------------- #

    if not (request.is_ajax() and request.method == "POST"):
        return_obj["success"] = False
        return_obj["message"] = "Unable to communicate with server."
        return_obj["results"] = {}

        return JsonResponse(return_obj)

    # ----------------------------- #
    #   GETS DATA FROM JAVASCRIPT   #
    # ----------------------------- #

    try:
        action_request = str(request.POST.get("actionRequest"))
        form_body = str(request.POST.get("formBody"))
        res_title = str(request.POST.get("resTitle"))
        res_abstract = str(request.POST.get("resAbstract"))
        res_keywords = str(request.POST.get("resKeywords")).split(",")
        res_access = str(request.POST.get("resAccess"))
        res_filename = res_title.replace(" ", "")[:10]
        selected_resources = map(int, (request.POST.get("checkedIds")).split(','))
        res_data = {"request": request,
                    "form_body": form_body,
                    "res_title": res_title,
                    "res_abstract": res_abstract,
                    "res_keywords": res_keywords,
                    "res_access": res_access,
                    "res_filename": res_filename,
                    "selected_resources": selected_resources
                    }

    except Exception, error_message:
        print traceback.format_exc()
        return_obj["success"] = False
        return_obj["message"] = "We encountered a problem while loading your resource data."
        return_obj["results"] = str(error_message)

        return JsonResponse(return_obj)

    # ------------------------- #
    #   GETS HYDROSHARE OAUTH   #
    # ------------------------- #

    try:
        hs_api = get_o_auth_hs(request)
        hs_version = hs_api.hostname

    except Exception, error_message:
        return_obj["success"] = False
        return_obj["message"] = "We were unable to authenticate your HydroShare sign-in."
        return_obj["results"] = str(error_message)

        return JsonResponse(return_obj)

    # ------------------------------- #
    #   CREATES HYDROSHARE RESOURCE   #
    # ------------------------------- #

    try:
        actions = {"ts": create_ts_resource,
                   "update": None,
                   "refts": create_refts_resource}

        processed_data = actions[action_request](res_data)

        res_type = processed_data["res_type"]
        res_filepath = processed_data["res_filepath"]
        res_filename = res_filename + processed_data["file_extension"]
        res_status = processed_data["parse_status"]

        return_status = []
        if action_request == "ts":
            for status in res_status:
                if status["res_status"] != "Success":
                    return_status.append(status["res_status"] + " for " + status["res_name"])
            if return_status:
                open(res_filepath, "w").close()
                return_obj["success"] = False
                return_obj["message"] = "PARSE_ERROR"
                return_obj["results"] = return_status

                return JsonResponse(return_obj)

        print "Attempting to create HydroShare Resource"
        resource_id = hs_api.createResource(res_type, res_title, abstract=res_abstract, keywords=res_keywords)

        try:
            with open(res_filepath, "rb") as res_file:
                hs_api.addResourceFile(resource_id, resource_file=res_file, resource_filename=res_filename)
            res_file.close()
            hs_api.getResourceFile(resource_id, res_filename)
            if hs_api.getSystemMetadata(resource_id)["resource_title"] == "Untitled resource":
                hs_api.deleteResource(resource_id)
                raise Exception
        except:
            hs_api.deleteResource(resource_id)
            raise Exception

    except Exception, error_message:
        print traceback.format_exc()
        print error_message
        return_obj['success'] = False
        return_obj['message'] = "We were unable to create your resource."
        return_obj['results'] = "Server Error: " + str(traceback.format_exc)

        return JsonResponse(return_obj)

    # --------------------------- #
    #   SETS RESOURCE AS PUBLIC   #
    # --------------------------- #

    if res_access == 'public':
        public = False
        timeout = time.time() + 20
        while public is False or time.time() < timeout:
            try:
                hs_api.setAccessRules(resource_id, public=True)
                public = True
            except:
                time.sleep(2)

        if public is False:
            return_obj['success'] = False
            return_obj['message'] = 'Request timed out.'
            return_obj['results'] = {}

            return JsonResponse(return_obj)

    # --------------------------------- #
    #   RESOURCE CREATED SUCCESSFULLY   #
    # --------------------------------- #

    return_obj['success'] = True
    return_obj['message'] = 'Resource created successfully'
    return_obj['results'] = {'resource_id': resource_id, 'hs_version': hs_version}

    TethysWorkspace(get_user_workspace(request)).clear()

    return JsonResponse(return_obj)
