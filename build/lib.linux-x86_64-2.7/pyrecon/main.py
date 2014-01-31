'''Main, overarching functions.'''
from pyrecon.classes import Section, Series
import os, re

def openSeries(path):
    '''Returns a Series object with associated Sections from the same directory.'''
    # Search path for .ser or .ser in path as a directory
    if '.ser' in path:
        series = Series(path)     
    else:
        series = Series([f for f in os.listdir(path) if '.ser' in f].pop())
    # Build directory variables for locating section files
    ser = os.path.basename(path)
    inpath = os.path.dirname(path)+'/'
    serfixer = re.compile(re.escape('.ser'), re.IGNORECASE)
    sername = serfixer.sub('', ser)
    # look for files with 'seriesname'+'.'+'number'
    p = re.compile('^'+sername+'[.][0-9]*$')
    sectionlist = [f for f in os.listdir(inpath) if p.match(f)]
    # create and append Sections for each section file
    for sec in sectionlist:
        section = Section(inpath+sec)
        series.update(section)
    # sort sections by index
    series.sections = sorted(series.sections, key=lambda Section: Section.index)
    return series

def merge(path1, path2, outputDirectory): #===
    return

def curate(path): #===
    return

def excel(path): #===
    return

def calibrate(path): #===
    return