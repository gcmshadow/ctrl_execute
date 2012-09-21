#!/usr/bin/env python

# 
# LSST Data Management System
# Copyright 2008, 2009, 2010 LSST Corporation.
# 
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the LSST License Statement and 
# the GNU General Public License along with this program.  If not, 
# see <http://www.lsstcorp.org/LegalNotices/>.
#

from __future__ import with_statement
import re, sys, os, os.path, shutil, subprocess
import optparse, traceback, time
from datetime import datetime
import lsst.pex.config as pexConfig
from string import Template
from TemplateWriter import TemplateWriter
from CondorConfig import CondorConfig
import eups

class EnvString:

    ##
    # given a string, look for any $ prefixed word, attempt to subsitute
    # an environment variable with that name.  
    #
    # @throw exception if the environment variable doesn't exist
    #
    # Return the resulting string
    def resolve(strVal):
        p = re.compile('\$[a-zA-Z0-9_]+')
        retVal = strVal
        exprs = p.findall(retVal)
        for i in exprs:
            var = i[1:]
            val = os.getenv(var, None)
            if val == None:
                raise RuntimeError("couldn't find environment variable "+i)
                sys.exit(120)
            retVal = p.sub(val,retVal,1)
        return retVal
    resolve = staticmethod(resolve)

class Configurator(object):
    def __init__(self, opts):

        self.opts = opts

        self.defaults = {}
        self.commandLineDefaults = {}
        self.commandLineDefaults["USER_NAME"] = os.getlogin()
        self.commandLineDefaults["USER_HOME"] = os.getenv('HOME')
        
        self.commandLineDefaults["DEFAULT_ROOT"]  = self.opts.defaultRoot
        self.commandLineDefaults["LOCAL_SCRATCH"] = self.opts.localScratch
        self.commandLineDefaults["DATA_DIRECTORY"] = self.opts.dataDirectory
        self.commandLineDefaults["IDS_PER_JOB"] = self.opts.idsPerJob
        self.commandLineDefaults["nodeSet"] = self.opts.nodeSet
        self.commandLineDefaults["INPUT_DATA_FILE"] = self.opts.inputDataFile
        self.commandLineDefaults["FILE_SYSTEM_DOMAIN"] = self.opts.fileSystemDomain
        self.commandLineDefaults["EUPS_PATH"] = self.opts.eupsPath

        # override user name, if given
        if self.opts.user_name is not None:
            self.commandLineDefaults["USER_NAME"] = self.opts.user_name
        
        # override user home, if given
        if self.opts.user_home is not None:
            self.commandLineDefaults["USER_HOME"] = self.opts.user_home

        if self.opts.runid is not None:
            self.runid = self.opts.runid
        else:
            self.runid = self.createRunId()
        
        self.platform = self.opts.platform
        self.commandLineDefaults["COMMAND"] = self.opts.command
        if self.commandLineDefaults["INPUT_DATA_FILE"] is not None:
            self.commandLineDefaults["COMMAND"] = self.commandLineDefaults["COMMAND"]+" ${id_option}"

        self.outputFileName = "/tmp/%s_config.py" % (self.runid)
        
    def createRunId(self):
        now = datetime.now()
        runid = "%s_%02d_%02d%02d_%02d%02d%02d" % (os.getlogin(), now.year, now.month, now.day, now.hour, now.minute, now.second)
        return runid

    def getSetupPackages(self):
        e = eups.Eups()
        setupProducts = e.getSetupProducts()
        a = ""
        # write out all setup products, except those that are setup locally.
        for i in setupProducts:
            if i.version.startswith("LOCAL:") == False:
                a = a + "setup -j %s %s\\n\\\n" % (i.name, i.version)
        return a

        return setupProducts
    def load(self, name):
        resolvedName = EnvString.resolve(name)
        configuration = CondorConfig()
        configuration.load(resolvedName)
        self.defaults = {}
        
        tempDefaultRoot = Template(configuration.platform.defaultRoot)
        self.defaults["DEFAULT_ROOT"] = tempDefaultRoot.substitute(USER_NAME=self.commandLineDefaults["USER_NAME"])
        #self.defaults["DEFAULT_ROOT"] = EnvString.resolve(configuration.platform.defaultRoot)
        tempLocalScratch = Template(configuration.platform.localScratch)
        self.defaults["LOCAL_SCRATCH"] = tempLocalScratch.substitute(USER_HOME=self.commandLineDefaults["USER_HOME"])
        
        #self.defaults["LOCAL_SCRATCH"] = EnvString.resolve(configuration.platform.localScratch)
        self.defaults["IDS_PER_JOB"] = configuration.platform.idsPerJob
        self.defaults["DATA_DIRECTORY"] = EnvString.resolve(configuration.platform.dataDirectory)
        self.defaults["FILE_SYSTEM_DOMAIN"] = configuration.platform.fileSystemDomain
        self.defaults["EUPS_PATH"] = configuration.platform.eupsPath
        # TODO:  Change this to do it the eups way when the new package
        # issue is resolved.
        #platform_dir = "$CTRL_PLATFORM_"+self.opts.platform.upper()+"_DIR"
        #platform_dir = EnvString.resolve(platform_dir)
        platform_dir = eups.productDir("ctrl_platform_"+self.opts.platform)
        self.defaults["PLATFORM_DIR"] = platform_dir

    def createConfiguration(self, input):
        resolvedInputName = EnvString.resolve(input)
        if self.opts.verbose == True:
            print "creating configuration using ",resolvedInputName
        template = TemplateWriter()
        substitutes = self.defaults.copy()
        for key in self.commandLineDefaults:
            val = self.commandLineDefaults[key]
            if val is not None:
                substitutes[key] = self.commandLineDefaults[key]

        substitutes["CTRL_EXECUTE_SETUP_PACKAGES"] = self.getSetupPackages()
        
        if self.opts.verbose == True:
            print "writing new configuration to ",self.outputFileName
        template.rewrite(resolvedInputName, self.outputFileName, substitutes)
        return self.outputFileName

    def isVerbose(self):
        return self.opts.verbose

    def getParameter(self,value):
        val = self.commandLineDefaults[value]
        if val == None:
            val =  self.defaults[value]
        return val

    def getRunid(self):
        return self.runid
