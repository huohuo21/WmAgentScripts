#!/usr/bin/env python
from assignSession import *
from utils import workflowInfo, getWorkflows, siteInfo
import reqMgrClient
import json
import os
import optparse
from collections import defaultdict

def equalizor(url , specific = None):

    if not specific:
        workflows = getWorkflows(url, status='running-closed', details=True)
        workflows.extend(getWorkflows(url, status='running-open', details=True))

    ## start from scratch
    modifications = defaultdict(dict)
    ## define regionality site => fallback allowed. feed on an ssb metric ??
    mapping = defaultdict(list)
    reversed_mapping = defaultdict(list)
    regions = defaultdict(list)
    SI = siteInfo()
    for site in SI.sites_ready:
        region = site.split('_')[1]
        regions[region] = [region] 

    for site in SI.sites_ready:
        region = site.split('_')[1]
        mapping[site] = [fb for fb in SI.sites_ready if any(['_%s_'%(reg) in fb for reg in regions[region]])and fb!=site]
    
    for site,fallbacks in mapping.items():
        for fb in fallbacks:
            reversed_mapping[fb].append(site)

    ## this is the fallback mapping
    #print json.dumps( mapping, indent=2)
    #print json.dumps( reversed_mapping, indent=2)

    def running_idle( wfi , task_name):
        gmon = wfi.getGlideMon()
        if not gmon: return (0,0)
        if not task_name in gmon: return (0,0)
        return (gmon[task_name]['Running'], gmon[task_name]['Idle'])

    def needs_action( wfi, task):
        task_name = task.pathName.split('/')[-1]
        running, idled = running_idle( wfi, task_name)
        if not idled and not running : return False, task_name, running, idled
        if (not running and idled) or (idled / float(running) > 0.3):
            return True, task_name, running, idled
        else:
            return False, task_name, running, idled

    def getcampaign( task ):
        taskname = task.pathName.split('/')[-1]
        if hasattr( task, 'prepID'):
            return task.prepID.split('-')[1]
        elif taskname.count('-')>=1:
            return taskname.split('-')[1]
        else:
            return None

    for wfo  in session.query(Workflow).filter(Workflow.status == 'away').all():
        if specific and not specific in wfo.name: 
            continue
        if specific:
            wfi = workflowInfo(url, wfo.name)
        else:
            cached = filter(lambda d : d['RequestName']==wfo.name, workflows)
            if not cached : continue
            wfi = workflowInfo(url, wfo.name, request = cached[0])
        
        tasks_and_campaigns = []
        for task in wfi.getWorkTasks():
            tasks_and_campaigns.append( (task, getcampaign(task) ) )

        ## now parse this for action
        for task,campaign in tasks_and_campaigns:
            #print task.pathName
            #print campaign
            if campaign == 'RunIIWinter15wmLHE':
                if task.taskType == 'Processing':
                    needs, task_name, running, idled = needs_action(wfi, task)
                    if needs:
                        print task_name,"of",wfo.name,"running",running,"and pending",idled,"taking action : ReplaceSiteWhitelist"
                        set_to = wfi.request['SiteWhitelist']
                        modifications[wfo.name][task.pathName] = { "ReplaceSiteWhitelist" : set_to ,"Running" : running, "Pending" : idled}
                    else:
                        print task_name,"of",wfo.name,"running",running,"and pending"
            if campaign == 'RunIIFall15DR76':
                ## we should add all sites that hold the secondary input if any
                secondary_locations = ['T1_ES_PIC','T2_US_Purdue','T2_UK_SGrid_RALPP','T2_BE_IIHE','T2_DE_DESY','T2_IT_Legnaro','T2_US_Caltech','T1_DE_KIT','T2_UK_London_Brunel','T2_IT_Pisa','T1_US_FNAL','T2_IT_Rome','T2_US_Florida','T1_IT_CNAF','T1_RU_JINR','T2_UK_London_IC','T2_US_Nebraska','T2_FR_CCIN2P3','T2_US_UCSD','T2_ES_CIEMAT','T1_FR_CCIN2P3','T2_US_Wisconsin','T2_US_MIT','T2_DE_RWTH','T1_UK_RAL','T2_US_Vanderbilt','T2_CH_CERN']
                ## should discover the above from secondary location (remember to cache this)
                #(lheinput,primary,parent,secondary, sites_allowed) = wfh.getSiteWhiteList()

                ## removing the ones in the site whitelist already since they encode the primary input location
                augment_by = list(set(secondary_locations)- set(wfi.request['SiteWhitelist']))
                if task.pathName.endswith('_0'):
                    needs, task_name, running, idled = needs_action(wfi, task)
                    if needs:
                        ## the step with an input ought to be the digi part : make this one go anywhere
                        modifications[wfo.name][task.pathName] = { "AddWhitelist" : augment_by , "Running" : running, "Pending" : idled}
                        print task_name,"of",wfo.name,"running",running,"and pending",idled,"taking action : AddWhitelist"
                    else:
                        print task_name,"of",wfo.name,"running",running,"and pending",idled
    interface = {'mapping' : mapping, 
                 'reversed_mapping' : reversed_mapping,
                 'modifications' : {}}
    if options.augment:
        interface['modifications'] = json.loads( open('/afs/cern.ch/user/c/cmst2/www/unified/equalizor.json').read())['modifications']
    interface['modifications'].update( modifications )
    open('/afs/cern.ch/user/c/cmst2/www/unified/equalizor.json.new','w').write( json.dumps( interface, indent=2))
    os.system('mv /afs/cern.ch/user/c/cmst2/www/unified/equalizor.json.new /afs/cern.ch/user/c/cmst2/www/unified/equalizor.json')
            

if __name__ == "__main__":
    url = 'cmsweb.cern.ch'

    parser = optparse.OptionParser()
    parser.add_option('-a','--augment',help='add on top of the document', default=False, action='store_true')
    (options,args) = parser.parse_args()
    spec=None
    if len(args)!=0:
        spec = args[0]

    equalizor(url, spec)

