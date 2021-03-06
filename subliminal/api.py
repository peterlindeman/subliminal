# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import collections
import io
import logging
import operator
import os.path
from .providers import ProviderManager
from .subtitle import get_subtitle_path


logger = logging.getLogger(__name__)


def list_subtitles(videos, languages, providers=None, provider_configs=None):
    """List subtitles for `videos` with the given `languages` using the specified `providers`

    :param videos: videos to list subtitles for
    :type videos: set of :class:`~subliminal.video.Video`
    :param languages: languages of subtitles to search for
    :type languages: set of :class:`babelfish.Language`
    :param providers: providers to use, if not all
    :type providers: list of string or None
    :param provider_configs: configuration for providers
    :type provider_configs: dict of provider name => provider constructor kwargs or None
    :return: found subtitles
    :rtype: dict of :class:`~subliminal.video.Video` => [:class:`~subliminal.subtitle.Subtitle`]

    """
    subtitles = collections.defaultdict(list)
    with ProviderManager(providers, provider_configs) as pm:
        for video in videos:
            logger.info('Listing subtitles for %r', video)
            video_subtitles = pm.list_subtitles(video, languages)
            logger.info('Found %d subtitles', len(video_subtitles))
            subtitles[video].extend(video_subtitles)
    return subtitles


def download_subtitles(subtitles, provider_configs=None):
    """Download subtitles

    :param subtitles: subtitles to download
    :type subtitles: list of :class:`~subliminal.subtitle.Subtitle`
    :param provider_configs: configuration for providers
    :type provider_configs: dict of provider name => provider constructor kwargs or None

    """
    with ProviderManager(provider_configs=provider_configs) as pm:
        for subtitle in subtitles:
            logger.info('Downloading subtitle %r', subtitle)
            pm.download_subtitle(subtitle)


def download_best_subtitles(videos, languages, providers=None, provider_configs=None, min_score=0,
                            hearing_impaired=False):
    """Download the best subtitles for `videos` with the given `languages` using the specified `providers`

    :param videos: videos to download subtitles for
    :type videos: set of :class:`~subliminal.video.Video`
    :param languages: languages of subtitles to download
    :type languages: set of :class:`babelfish.Language`
    :param providers: providers to use for the search, if not all
    :type providers: list of string or None
    :param provider_configs: configuration for providers
    :type provider_configs: dict of provider name => provider constructor kwargs or None
    :param int min_score: minimum score for subtitles to download
    :param bool hearing_impaired: download hearing impaired subtitles

    """
    downloaded_subtitles = collections.defaultdict(list)
    with ProviderManager(providers, provider_configs) as pm:
        for video in videos:
            # list
            logger.info('Listing subtitles for %r', video)
            video_subtitles = pm.list_subtitles(video, languages)
            logger.info('Found %d subtitles', len(video_subtitles))

            # download
            downloaded_languages = set()
            for subtitle, score in sorted([(s, s.compute_score(video)) for s in video_subtitles],
                                          key=operator.itemgetter(1), reverse=True):
                if score < min_score:
                    logger.info('No subtitle with score >= %d', min_score)
                    break
                if subtitle.hearing_impaired != hearing_impaired:
                    logger.debug('Skipping subtitle: hearing impaired != %r', hearing_impaired)
                    continue
                if subtitle.language in downloaded_languages:
                    logger.debug('Skipping subtitle: %r already downloaded', subtitle.language)
                    continue
                logger.info('Downloading subtitle %r with score %d', subtitle, score)
                if pm.download_subtitle(subtitle):
                    downloaded_languages.add(subtitle.language)
                    downloaded_subtitles[video].append(subtitle)
                if downloaded_languages == languages:
                    logger.debug('All languages downloaded')
                    break
    return downloaded_subtitles


def save_subtitles(subtitles, single=False, folder_path=None):
    """Save subtitles on disk next to the video or in a specific folder if `folder_path` is specified

    :param bool single: download with .srt extension if ``True``, add language identifier otherwise
    :param folder_path: path to folder where to save the subtitles, if any
    :type folder_path: string or None

    """
    for video, video_subtitles in subtitles.items():
        saved_languages = set()
        for video_subtitle in video_subtitles:
            if video_subtitle.content is None:
                logger.debug('Skipping subtitle %r: no content', video_subtitle)
                continue
            if video_subtitle.language in saved_languages:
                logger.debug('Skipping subtitle %r: language already saved', video_subtitle)
                continue
            subtitle_path = get_subtitle_path(video.name, None if single else video_subtitle.language)
            if folder_path is not None:
                subtitle_path = os.path.join(folder_path, os.path.split(subtitle_path)[1])
            logger.info('Saving %r to %r', video_subtitle, subtitle_path)
            with io.open(subtitle_path, 'w', encoding='utf-8') as f:
                f.write(video_subtitle.content)
            saved_languages.add(video_subtitle.language)
            if single:
                break
