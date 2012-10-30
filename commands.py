import os, os.path
import shutil
import urllib, urllib2
import subprocess
import simplejson as json
import yaml

from play.utils import *

DEPS = ['deps-for-appmode']
BM = ['build-module-for-appmode']
COMMANDS = DEPS + BM
HELP = {
    'deps-for-appmode': 'Module for Dependencies Management. Supports multiple application modes. Resolve and retrieve project dependencies',
    'build-module-for-appmode': 'Build and package a module, ignore some files defined optionally in application.conf'
}

def execute(**kargs):
    args = kargs.get("args")
    play_env = kargs.get("env")

    command = kargs.get("command")
    app = kargs.get("app")
    args = kargs.get("args")
    play_env = kargs.get("env")

    print 'command %s' % command
    if command in DEPS:
        solveDeps(app, args, play_env)
    elif command in BM:
        buildModuleMulti(app, args, play_env)

def solveDeps(app, args, play_env):
    force = "false"
    trim = "false"
    if args.count('--forceCopy') == 1:
        args.remove('--forceCopy')
        force = "true"
        
    if args.count('--forProd') == 1:
        args.remove('--forProd')
        force = "true"
        trim = "true"

    classpath = app.getClasspath()

    add_options = ['-Dapplication.path=%s' % (app.path), '-Dframework.path=%s' % (play_env['basedir']), '-Dplay.id=%s' % play_env['id'], '-Dplay.version=%s' % play_env['version'], '-Dplay.forcedeps=%s' % (force), '-Dplay.trimdeps=%s' % (trim)]
    if args.count('--verbose'):
        add_options.append('-Dverbose')
    if args.count('--sync'):
        add_options.append('-Dsync')
    if args.count('--debug'):
        add_options.append('-Ddebug')
    if args.count('--clearcache'):
        add_options.append('-Dclearcache')
    if args.count('--jpda'):
        print "~ Waiting for JPDA client to continue"
        add_options.extend(['-Xdebug', '-Xrunjdwp:transport=dt_socket,address=8888,server=y,suspend=y'])
    for arg in args:
        if arg.startswith("-D"):
            add_options.append(arg)
    wdcp = app.getClasspath()
    cp_args = ':'.join(wdcp)
    if os.name == 'nt':
        cp_args = ';'.join(wdcp)
    java_cmd = [app.java_path()] + add_options + ['-classpath', cp_args ,'play.modules.deployment.DependenciesManagerForMultiApplicationMode']

    return_code = subprocess.call(java_cmd, env=os.environ)
    if 0 != return_code:
        sys.exit(return_code);


def buildModuleMulti(app, args, env):
    ftb = env["basedir"]
    version = None
    name = None
    fwkMatch = None
    try:
        optlist, args = getopt.getopt(args, '', ['framework=', 'version=', 'require=','mode='])
        for o, a in optlist:
            if o in ('--framework'):
                ftb = a
            if o in ('--version'):
                version = a
            if o in ('--require'):
                fwkMatch = a
            if o in ('--mode'):
                mode = a
    except getopt.GetoptError, err:
        print "~ %s" % str(err)
        print "~ "
        sys.exit(-1)
    print 'mode: '+mode

    deps_file = os.path.join(app.path, 'conf', 'dependencies.yml')
    if os.path.exists(deps_file):
        f = open(deps_file)
        deps = yaml.load(f.read())
        self = deps["self"].split(" ")
        versionCandidate = self.pop()
        name = self.pop()
        version = versionCandidate
        for dep in deps["require"]:
            if isinstance(dep, basestring):
                splitted = dep.split(" ")
                if len(splitted) == 2 and splitted[0] == "play":
                    fwkMatch = splitted[1]
        f.close

    if name is None:
        name = os.path.basename(app.path)
    if version is None:
        version = raw_input("~ What is the module version number? ")
    if fwkMatch is None:
        fwkMatch = raw_input("~ What are the playframework versions required? ")

    build_file = os.path.join(app.path, 'build.xml')
    if os.path.exists(build_file):
        print "~"
        print "~ Building..."
        print "~"
        os.system('ant -f %s -Dplay.path=%s' % (build_file, ftb) )
        print "~"

    mv = '%s-%s' % (name, version)
    print("~ Packaging %s ... " % mv)

    dist_dir = os.path.join(app.path, 'dist')
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    os.mkdir(dist_dir)

    manifest = os.path.join(app.path, 'manifest')
    manifestF = open(manifest, 'w')
    manifestF.write('version=%s\nframeworkVersions=%s\n' % (version, fwkMatch))
    manifestF.close()

    zip = zipfile.ZipFile(os.path.join(dist_dir, '%s.zip' % mv), 'w', zipfile.ZIP_STORED)
    print ' ~ mode "%s"' % mode
    ignoreList = 'ignore.for.build.%s' % mode
    print ' ~ application variable: ' + ignoreList
    ignoreForBuild = app.readConf(ignoreList)
    print ' ~  ~  ignore expression from application.conf: %s ' % ignoreForBuild
    ignoreForBuildList = ignoreForBuild.split(",")
    for (dirpath, dirnames, filenames) in os.walk(app.path):
        dirname = app.toRelative(dirpath);
        message = "add: %s" % (dirname)
        if dirpath == dist_dir:
            continue
        if dirname.find(os.sep + '.') > -1 and ( len(ignoreForBuildList) > 1 or ignorePath(dirname, ignoreForBuildList) == 1 ):
            continue
        print  ' ~  ~  '+message
        for file in filenames:
            if file.find('~') > -1 or file.endswith('.iml') or file.startswith('.'):
                continue
            zip.write(os.path.join(dirpath, file), os.path.join(dirpath[len(app.path):], file))
    zip.close()

    os.remove(manifest)

    print "~"
    print "~ Done!"
    print "~ Package is available at %s" % os.path.join(dist_dir, '%s.zip' % mv)
    print "~"

def ignorePath(path, ignoredDirectories):
    for word in ignoredDirectories:
        if word in path:
            return 1
    return 0