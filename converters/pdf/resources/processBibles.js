require("babel-polyfill"); // required for async/await
import path from 'path-extra';
import fs from 'fs-extra';
import sourceContentUpdater from 'tc-source-content-updater';
import yaml from 'js-yaml';
import yargs from 'yargs';

const RESOURCE_ORG = "unfoldingWord";

let SourceContentUpdater = null;

/**
 * Returns an array of versions found in the path that start with [vV]\d
 * @param {String} resourcePath - base path to search for versions
 * @return {Array} - array of versions, e.g. ['v1', 'v10', 'v1.1']
 */
function getVersionsInPath(resourcePath) {
  if (!resourcePath || !fs.pathExistsSync(resourcePath)) {
    return null;
  }
  const isVersionDirectory = (name) => {
    const fullPath = path.join(resourcePath, name);
    return fs.lstatSync(fullPath).isDirectory() && name.match(/^v\d/i);
  };
  return sortVersions(fs.readdirSync(resourcePath).filter(isVersionDirectory));
}

/**
 * Returns a sorted an array of versions so that numeric parts are properly ordered (e.g. v10a < v100)
 * @param {Array} versions - array of versions unsorted: ['v05.5.2', 'v5.5.1', 'V6.21.0', 'v4.22.0', 'v6.1.0', 'v6.1a.0', 'v5.1.0', 'V4.5.0']
 * @return {Array} - array of versions sorted:  ["V4.5.0", "v4.22.0", "v5.1.0", "v5.5.1", "v05.5.2", "v6.1.0", "v6.1a.0", "V6.21.0"]
 */
function sortVersions(versions) {
  // Don't sort if null, empty or not an array
  if (!versions || !Array.isArray(versions)) {
    return versions;
  }
  // Only sort of all items are strings
  for (let i = 0; i < versions.length; ++i) {
    if (typeof versions[i] !== 'string') {
      return versions;
    }
  }
  versions.sort((a, b) => String(a).localeCompare(b, undefined, {numeric: true}));
  return versions;
}

/**
 * Return the full path to the highest version folder in resource path
 * @param {String} resourcePath - base path to search for versions
 * @return {String} - path to highest version
 */
function getLatestVersionInPath(resourcePath) {
  const versions = sortVersions(getVersionsInPath(resourcePath));
  if (versions && versions.length) {
    return path.join(resourcePath, versions[versions.length - 1]);
  }
  return null; // return illegal path
}

const processOLBible = (resource) => {
  const repo = resource.languageId + '_' + resource.resourceId;
  const repoPath = path.join(reposDir, repo);
  const manifest = yaml.load(fs.readFileSync(path.join(repoPath, 'manifest.yaml'), 'utf8'));
  const version = manifest['dublin_core']['version'];
  const biblePath = path.join(resourcesDir, resource.languageId, 'bibles', resource.resourceId, 'v' + version+"_"+RESOURCE_ORG);
  console.log("BIBLE " + resource.resourceId + ": " + biblePath + ", repoPath: " + repoPath)
  console.log("CALLING SourceContentUpdater.parseBiblePackage(", resource, ", ", repoPath, ", ", biblePath, ")")
  SourceContentUpdater.parseBiblePackage(resource, repoPath, biblePath);
  const twGroupDataPath = path.join(resourcesDir, resource.languageId, 'translationHelps', 'translationWords', 'v' + version+"_"+RESOURCE_ORG);
  console.log("TW " + resource.resourceId + ": " + twGroupDataPath);
  console.log(resource, biblePath, twGroupDataPath);
  var ret = SourceContentUpdater.generateTwGroupDataFromAlignedBible(resource, biblePath, twGroupDataPath);
  console.log(ret);
};

const processUWBible = (resource) => {
  const repo = resource.languageId + '_' + resource.resourceId;
  const repoPath = path.join(reposDir, repo);
  const manifest = yaml.load(fs.readFileSync(path.join(repoPath, 'manifest.yaml'), 'utf8'));
  const version = manifest['dublin_core']['version'];
  const biblePath = path.join(resourcesDir, resource.languageId, 'bibles', resource.resourceId, 'v' + version+"_"+RESOURCE_ORG);
  console.log("BIBLE " + resource.resourceId + ": " + biblePath)
  SourceContentUpdater.parseBiblePackage(resource, repoPath, biblePath);
};

const processTA = (resource) => {
  const taRepo = resource.languageId + '_ta';
  const taRepoPath = path.join(reposDir, taRepo);
  const taManifest = yaml.load(fs.readFileSync(path.join(taRepoPath, 'manifest.yaml'), 'utf8'));
  const taVersion = taManifest['dublin_core']['version'];
  const taGroupDataPath = path.join(resourcesDir, resource.languageId, 'translationHelps', 'translationAcademy', 'v' + taVersion+"_"+RESOURCE_ORG);
  console.log("TA " + resource.resourceId + ": " + taGroupDataPath);
  SourceContentUpdater.processTranslationAcademy(resource, taRepoPath, taGroupDataPath);
};

const processTW = (resource) => {
  const twRepo = resource.languageId + '_tw';
  const twRepoPath = path.join(reposDir, twRepo);
  const twManifest = yaml.load(fs.readFileSync(path.join(twRepoPath, 'manifest.yaml'), 'utf8'));
  const twVersion = twManifest['dublin_core']['version'];
  const twGroupDataPath = path.join(resourcesDir, resource.languageId, 'translationHelps', 'translationWords', 'v' + twVersion+"_"+RESOURCE_ORG);
  console.log("TW " + resource.resourceId + ": " + twGroupDataPath);
  SourceContentUpdater.processTranslationWords(resource, twRepoPath, twGroupDataPath);
};

const processTN = (resource) => {
  const tnRepo = resource.languageId + '_tn';
  const tnRepoPath = path.join(reposDir, tnRepo);
  const tnManifest = yaml.load(fs.readFileSync(path.join(tnRepoPath, 'manifest.yaml'), 'utf8'));
  const tnVersion = tnManifest['dublin_core']['version'];
  const tnGroupDataPath = path.join(resourcesDir, resource.languageId, 'translationHelps', 'translationNotes', 'v' + tnVersion+"_"+RESOURCE_ORG);
  console.log("TN: " + tnGroupDataPath);
  SourceContentUpdater.processTranslationNotes(resource, tnRepoPath, tnGroupDataPath, resourcesDir);
};

const processBibles = (langId, reposDir, resourcesDir, ultId, ustId) => {
  SourceContentUpdater = new sourceContentUpdater();
  fs.mkdirSync(resourcesDir, {recursive: true});
  if (fs.pathExistsSync(path.join(reposDir, 'hbo_uhb'))) {
    processOLBible({
      owner: RESOURCE_ORG,
      languageId: 'hbo',
      resourceId: 'uhb',
      downloadUrl: 'https://test.com'
    });
  }
  if (fs.pathExistsSync(path.join(reposDir, 'el-x-koine_ugnt'))) {
    processOLBible({
      owner: RESOURCE_ORG,
      languageId: 'el-x-koine',
      resourceId: 'ugnt',
      downloadUrl: 'https://test.com'
    });
  }
  if (ultId && fs.pathExistsSync(path.join(reposDir, langId + '_' + ultId))) {
    processUWBible({
      owner: RESOURCE_ORG,
      languageId: langId,
      resourceId: ultId,
      downloadUrl: 'https://test.com'
    });
  }
  if (ustId && fs.pathExistsSync(path.join(reposDir, langId + '_' + ustId))) {
    processUWBible({
      owner: RESOURCE_ORG,
      languageId: langId,
      resourceId: ustId,
      downloadUrl: 'https://test.com'
    });
  }
  if (fs.pathExistsSync(path.join(reposDir, langId + '_ta'))) {
    processTA({
      owner: RESOURCE_ORG,
      languageId: langId,
      resourceId: 'ta',
      downloadUrl: 'https://test.com'
    });
  }
  if (fs.pathExistsSync(path.join(reposDir, langId + '_tw'))) {
    processTW({
      owner: RESOURCE_ORG,
      languageId: langId,
      resourceId: 'tw',
      downloadUrl: 'https://test.com'
    });
  }
  if (fs.pathExistsSync(path.join(reposDir, langId + '_tn'))) {
    processTN({
      owner: RESOURCE_ORG,
      languageId: langId,
      resourceId: 'tn',
      downloadUrl: 'https://test.com'
    });
  }
};

const args = yargs.argv;

const resourcesDir = args.resources_dir
const reposDir = args.repos_dir
const lang = args.l || args.language || 'en';
const ultId = args.ult_id;
const ustId = args.ust_id;

if (!fs.existsSync(reposDir)) {
  throw Error('Parent of resources path does not exist: ' + reposDir);
}

processBibles(lang, reposDir, resourcesDir, ultId, ustId);
