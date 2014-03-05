#opensubtitles.org
#Subtitles service allowed by www.OpenSubtitles.org
#Language codes: http://www.opensubtitles.org/addons/export_languages.php

OS_API = 'http://plexapp.api.opensubtitles.org/xml-rpc'
OS_PLEX_USERAGENT = 'plexapp.com v9.0'
SUBTITLE_EXT = ['utf','utf8','utf-8','sub','srt','smi','rt','ssa','aqt','jss','ass','idx']

####################################################################################################
def Start():

  HTTP.CacheTime = CACHE_1DAY
  HTTP.Headers['User-Agent'] = OS_PLEX_USERAGENT

####################################################################################################
def opensubtitlesProxy():

  proxy = XMLRPC.Proxy(OS_API)
  username = Prefs['username'] if Prefs['username'] is not None else ''
  password = Prefs['password'] if Prefs['password'] is not None else ''
  token = proxy.LogIn(username, password, 'en', OS_PLEX_USERAGENT)['token']
  return (proxy, token)

####################################################################################################
def fetchSubtitles(proxy, token, part, media_id='', imdbID=''):

  # Remove(?) previously downloaded OS subs
  for l in part.subtitles:
    Log(" LANG : %s" % l)
    part.subtitles[l].validate_keys([])

  # !!!


  langList = [Prefs['langPref1']]

  if Prefs['langPref2'] != 'None' and Prefs['langPref1'] != Prefs['langPref2']:
    langList.append(Prefs['langPref2'])


  # Grab metadata for current library item
  xml_tree = XML.ElementFromURL('http://localhost:32400/library/metadata/%s/tree' % media_id, cacheTime=0)

  for l in langList:

    # Skip lookup for this language if we already have a sidecar subtitle in this language
    if len(xml_tree.xpath('//MediaStream[@type="3" and not(starts-with(@url, "media://")) and @language="%s"]' % l)) > 0:
      Log('Subtitle for language "%s" already present, skipping' % l)
      continue




    Log('Looking for match for GUID %s and size %d' % (part.openSubtitleHash, part.size))
    subtitleResponse = proxy.SearchSubtitles(token,[{'sublanguageid':l, 'moviehash':part.openSubtitleHash, 'moviebytesize':str(part.size)}])['data']
    #Log('hash/size search result: ')
    #Log(subtitleResponse)

    if subtitleResponse == False and imdbID != '': #let's try the imdbID, if we have one...
      subtitleResponse = proxy.SearchSubtitles(token,[{'sublanguageid':l, 'imdbid':imdbID}])['data']
      Log('Found nothing via hash, trying search with imdbid: %s' % imdbID)
      #Log(subtitleResponse)

    if subtitleResponse != False:
      for st in subtitleResponse: #remove any subtitle formats we don't recognize
        if st['SubFormat'] not in SUBTITLE_EXT:
          Log('Removing a subtitle of type: %s' % st['SubFormat'])
          subtitleResponse.remove(st)



      # NEW
      xml_tree = XML.ElementFromURL('http://localhost:32400/library/metadata/%s' % media_id, cacheTime=0)

      video_resolution = xml_tree.xpath('//Media/@videoResolution')[0]
      Log(video_resolution)
      is_hd = video_resolution >= 720
      Log(is_hd)
      video_frame_rate = xml_tree.xpath('//Media/@videoFrameRate')[0]
      Log(video_frame_rate)




      # /NEW


      st = sorted(subtitleResponse, key=lambda k: int(k['SubDownloadsCnt']), reverse=True)[0] #most downloaded subtitle file for current language

      subUrl = st['SubDownloadLink']
      subGz = HTTP.Request(subUrl, headers={'Accept-Encoding':'gzip'}).content
      subData = Archive.GzipDecompress(subGz)
      part.subtitles[Locale.Language.Match(st['SubLanguageID'])][subUrl] = Proxy.Media(subData, ext=st['SubFormat'])

    else:
      Log('No subtitles available for language %s' % l)

####################################################################################################
class OpenSubtitlesAgentMovies(Agent.Movies):

  name = 'OpenSubtitles.org'
  languages = [Locale.Language.NoLanguage]
  primary_provider = False
  contributes_to = ['com.plexapp.agents.imdb']

  def search(self, results, media, lang):

    results.Append(MetadataSearchResult(
      id    = media.primary_metadata.id.strip('t'),
      score = 100
    ))

  def update(self, metadata, media, lang):

    (proxy, token) = opensubtitlesProxy()

    for item in media.items:
      for part in item.parts:
        fetchSubtitles(proxy, token, part, media.id, metadata.id)

####################################################################################################
class OpenSubtitlesAgentTV(Agent.TV_Shows):

  name = 'OpenSubtitles.org'
  languages = [Locale.Language.NoLanguage]
  primary_provider = False
  contributes_to = ['com.plexapp.agents.thetvdb']

  def search(self, results, media, lang):

    results.Append(MetadataSearchResult(
      id    = 'null',
      score = 100
    ))

  def update(self, metadata, media, lang):

    (proxy, token) = opensubtitlesProxy()

    for s in media.seasons:
      # just like in the Local Media Agent, if we have a date-based season skip for now.
      if int(s) < 1900:
        for e in media.seasons[s].episodes:
          for i in media.seasons[s].episodes[e].items:
            for part in i.parts:
              fetchSubtitles(proxy, token, part)
