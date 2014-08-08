#!/usr/bin/env python

##########################################################################
#  
#  Gaia, task list organiser in with Caldav server sync.
#  
#  Copyright (C) 2013-2014 Dr Adam S. Candy.
#  Dr Adam S. Candy, contact@gaiaproject.org
#  
# This file is part of the Gaia project.
# 
# Gaia is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Gaia is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Gaia.  If not, see <http://www.gnu.org/licenses/>.
#
##########################################################################

class colour:
  red = ''
  redbright = ''
  cyan = ''
  cyanbright = ''
  blue = ''
  bluebright = ''
  yellow = ''
  yellowbright = ''
  green = ''
  greenbright = ''
  magenta = ''
  magentabright = ''
  grey = ''
  end = ''

class universe:
  timezone = None
  statefile = None
  dataroot = None
  logfile = None
  backuproot = None
  backupcalendars = None
  prowllast = None
  verbose = None
  debug = None
  errors = None
  now = None
  dry = None
  bufferreturned = None
  log = None
  killed = None
  calendarcache = None
  calendaraddresstoname = None
  calendarctag = None
  defaulttime = None
  principalurl = None
  # Might not be able to write to?  Do a test write?
  reportline = None
  reportcache = None
  auxlists = None
  category_order = None
  skipweekendlists = None
  interlude = None
  next_char = None
  routine = None

