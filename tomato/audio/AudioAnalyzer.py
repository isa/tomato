from predominantmelodymakam.PredominantMelodyMakam import \
    PredominantMelodyMakam
from pitchfilter.PitchFilter import PitchFilter
from tonicidentifier.TonicLastNote import TonicLastNote
from ahenkidentifier.AhenkIdentifier import AhenkIdentifier
from notemodel.NoteModel import NoteModel
from modetonicestimation.PitchDistribution import PitchDistribution
import numpy as np
from copy import deepcopy
import json
from matplotlib import gridspec
import matplotlib.pyplot as plt


class AudioAnalyzer(object):
    def __init__(self, verbose=False):
        self.verbose = verbose

        # extractors
        self._pitchExtractor = PredominantMelodyMakam()
        self._pitchFilter = PitchFilter()
        self._tonicIdentifier = TonicLastNote()
        self._noteModeler = NoteModel()
        self._pd_params = {'smooth_factor': 7.5, 'step_size': 7.5}

    def analyze(self, filepath, makam=None):
        # predominant melody extraction
        pitch = self.extract_pitch(filepath)

        # even though predominant melody calls pitch filter in Essentia,
        # it is not as goot as Sercan Atli's implementation in Python.
        pitch = self.filter_pitch(pitch)

        # tonic identification
        tonic = self.identify_tonic(pitch)

        # histogram computation
        pitch_distribution = self.compute_pitch_distribution(pitch, tonic)
        pitch_class_distribution = pitch_distribution.to_pcd()

        # makam recognition
        if makam is None:
            raise NotImplementedError('Makam recognition is not integrated.')

        # transposition (ahenk) identification
        ahenk = self.identify_ahenk(tonic, makam)

        # tuning analysis and stable pitch extraction
        stable_notes = self.get_stable_notes(pitch_distribution, tonic, makam)

        # return as a dictionary
        return {'pitch': pitch, 'tonic': tonic, 'ahenk': ahenk, 'makam': makam,
                'pitch_distribution': pitch_distribution,
                'pitch_class_distribution': pitch_class_distribution,
                'stable_notes': stable_notes}

    def extract_pitch(self, filename):
        if self.verbose:
            print("- Extracting predominant melody of " + filename)

        results = self._pitchExtractor.run(filename)
        pitch = results['settings']  # collapse the keys in settings
        pitch['pitch'] = results['pitch']

        return pitch

    def filter_pitch(self, pitch):
        if self.verbose:
            print("- Filtering predominant melody of " + pitch['source'])

        pitch_filt = deepcopy(pitch)
        pitch_filt['pitch'] = self._pitchFilter.run(pitch_filt['pitch'])

        return pitch_filt

    def identify_tonic(self, pitch):
        if self.verbose:
            print("- Identifying tonic from the predominant melody of " +
                  pitch['source'])

        tonic = self._tonicIdentifier.identify(pitch['pitch'])[0]

        # add the source audio file
        tonic['source'] = pitch['source']

        return tonic

    def identify_ahenk(self, tonic, makamstr):
        if self.verbose:
            print("- Identifying ahenk of " + tonic['source'])
        ahenk = AhenkIdentifier.identify(tonic['value'], makamstr)
        ahenk['source'] = tonic['source']

        return ahenk

    def compute_pitch_distribution(self, pitch, tonic):
        if self.verbose:
            print("- Computing pitch distribution of " + pitch['source'])

        return PitchDistribution.from_hz_pitch(
            np.array(pitch['pitch'])[:, 1], ref_freq=tonic['value'],
            smooth_factor=self._pd_params['smooth_factor'],
            step_size=self._pd_params['step_size'])

    def compute_class_pitch_distribution(self, pitch, tonic):
        if self.verbose:
            print("- Computing pitch class distribution of " + pitch['source'])

        return self.compute_pitch_distribution(pitch, tonic).to_pcd()

    def get_stable_notes(self, pitch_distribution, tonic, makamstr):
        if self.verbose:
            print("- Computing pitch class distribution of " + tonic['source'])

        return self._noteModeler.calculate_notes(pitch_distribution,
                                                 tonic['value'], makamstr)

    def set_pitch_extractor_params(self, **kwargs):
        if any(key not in self._pitchExtractor.__dict__.keys()
               for key in kwargs.keys()):
            raise KeyError("Possible parameters are: " + ', '.join(
                self._pitchExtractor.__dict__.keys()))

        for key, value in kwargs.items():
            setattr(self._pitchExtractor, key, value)

    def set_pitch_filter_params(self, **kwargs):
        if any(key not in self._pitchFilter.__dict__.keys()
               for key in kwargs.keys()):
            raise KeyError("Possible parameters are: " + ', '.join(
                self._pitchFilter.__dict__.keys()))

        for key, value in kwargs.items():
            setattr(self._pitchFilter, key, value)

    def set_tonic_identifier_params(self, **kwargs):
        if any(key not in self._tonicIdentifier.__dict__.keys()
               for key in kwargs.keys()):
            raise KeyError("Possible parameters are: " + ', '.join(
                self._tonicIdentifier.__dict__.keys()))

        for key, value in kwargs.items():
            setattr(self._tonicIdentifier, key, value)

    def set_pitch_distibution_params(self, **kwargs):
        if any(key not in self._pd_params.keys() for key in kwargs.keys()):
            raise KeyError("Possible parameters are: " + ', '.join(
                self._pd_params.keys()))

        for key, value in kwargs.items():
            self._pd_params[key] = value

    def set_note_modeler_params(self, **kwargs):
        if any(key not in self._noteModeler.__dict__.keys()
               for key in kwargs.keys()):
            raise KeyError("Possible parameters are: " + ', '.join(
                self._noteModeler.__dict__.keys()))

        for key, value in kwargs.items():
            setattr(self._noteModeler, key, value)

    @staticmethod
    def save_features(features, filepath=None):
        save_features = deepcopy(features)
        try:
            save_features['pitch_distribution'] = \
                save_features['pitch_distribution'].to_dict()
        except AttributeError:
            pass  # already converted to dict devoid of numpy stuff

        try:
            save_features['pitch_class_distribution'] = \
                save_features['pitch_class_distribution'].to_dict()
        except AttributeError:
            pass  # already converted to dict devoid of numpy stuff

        try:
            save_features['pitch']['pitch'] = save_features['pitch'][
                'pitch'].tolist()
        except AttributeError:
            pass  # already converted to list of lists

        if filepath is None:
            json.dumps(save_features, indent=4)
        else:
            json.dump(save_features, open(filepath, 'w'), indent=4)

    @staticmethod
    def load_features(filepath):
        try:
            features = json.load(open(filepath, 'r'))
        except IOError:
            features = json.loads(filepath)

        # instantiate pitch distribution objects
        features['pitch_distribution'] = PitchDistribution.from_dict(
            features['pitch_distribution'])
        features['pitch_class_distribution'] = PitchDistribution.from_dict(
            features['pitch_class_distribution'])

        return features

    @staticmethod
    def plot(features):
        pitch = np.array(deepcopy(features['pitch']['pitch']))
        pitch[pitch[:, 1] < 20.0, 1] = np.nan  # remove inaudible for plots
        pitch_distibution = features['pitch_distribution']
        stable_notes = deepcopy(features['stable_notes'])

        # create the figure with two subplots with different size and share-y
        fig = plt.figure()
        gs = gridspec.GridSpec(1, 2, width_ratios=[6, 1])
        ax1 = fig.add_subplot(gs[0])
        ax2 = fig.add_subplot(gs[1], sharey=ax1)
        plt.setp(ax2.get_yticklabels(), visible=False)

        # plot pitch track
        ax1.plot(pitch[:, 0], pitch[:, 1], 'g', label='Pitch', alpha=0.7)
        fig.subplots_adjust(wspace=0)

        # set xlim to the last time in the pitch track
        ax1.set_xlim([pitch[0, 0], pitch[-1, 0]])
        ax1.set_ylim([np.min(pitch_distibution.bins),
                      np.max(pitch_distibution.bins)])

        # Labels
        ax1.set_xlabel('Time (sec)')
        ax1.set_ylabel('Frequency (Hz)')

        # plot pitch distribution to the second subplot
        ax2.plot(pitch_distibution.vals, pitch_distibution.bins)

        # plot stable pitches to the second subplot
        max_rel_occur = 0
        for note_symbol, note in stable_notes.iteritems():
            # get the relative occurence of each note from the pitch
            # distribution
            dists = np.array([abs(note['stable_pitch']['value'] - dist_bin)
                              for dist_bin in pitch_distibution.bins])
            peak_ind = np.argmin(dists)
            note['rel_occur'] = pitch_distibution.vals[peak_ind]
            max_rel_occur = max([max_rel_occur, note['rel_occur']])

        ytick_vals = []
        for note_symbol, note in stable_notes.iteritems():
            if note['rel_occur'] > max_rel_occur * 0.1:
                ytick_vals.append(note['stable_pitch']['value'])

                # plot the performed frequency as a dashed line
                ax2.hlines(y=note['theoretical_pitch']['value'], xmin=0,
                           xmax=note['rel_occur'], linestyles='dashed')

                # mark notes
                if note['performed_interval']['value'] == 0.0:  # tonic
                    ax2.plot(note['rel_occur'], note['stable_pitch']['value'],
                             'cD', ms=10)
                else:
                    ax2.plot(note['rel_occur'], note['stable_pitch']['value'],
                             'cD', ms=6, c='r')

                # print note name, lift the text a little bit
                txt_x_val = (note['rel_occur'] +
                             0.03 * max(pitch_distibution.vals))
                txt_str = ', '.join(
                    [note_symbol,
                     str(int(round(note['performed_interval']['value']))) +
                     ' cents'])
                ax2.text(txt_x_val, note['stable_pitch']['value'], txt_str,
                         style='italic', horizontalalignment='left',
                         verticalalignment='center')

        # define xlim higher than the highest peak so the note names have space
        ax2.set_xlim([0, 1.2 * max(pitch_distibution.vals)])

        # remove the axis of the subplot 2
        ax2.axis('off')

        # set the frequency ticks and grids
        ax1.set_yticks(ytick_vals)
        ax1.yaxis.grid(True)

        ax2.set_yticks(ytick_vals)
        ax2.yaxis.grid(True)

        # remove spines from the second subplot
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        ax2.spines['bottom'].set_visible(False)
        ax2.spines['left'].set_visible(False)

        return fig, (ax1, ax2)
