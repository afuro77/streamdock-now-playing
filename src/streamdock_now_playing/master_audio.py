"""Windows default endpoint volume, deliberately independent of Spotify sessions."""
class MasterAudio:
    def __init__(self, endpoint=None): self.endpoint=endpoint
    def command(self, amount=None):
        if self.endpoint is None:
            from pycaw.pycaw import AudioUtilities
            endpoint=AudioUtilities.GetSpeakers().EndpointVolume
        else: endpoint=self.endpoint()
        if amount is None:
            endpoint.SetMute(not bool(endpoint.GetMute()),None)
        else:
            value=max(0,min(1,endpoint.GetMasterVolumeLevelScalar()+amount/100))
            endpoint.SetMasterVolumeLevelScalar(value,None)
        return 'MUTE' if endpoint.GetMute() else f'VOL {round(endpoint.GetMasterVolumeLevelScalar()*100)}%'
