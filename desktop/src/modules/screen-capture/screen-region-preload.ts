import { contextBridge, ipcRenderer } from 'electron';
import { IPC_CHANNELS } from '../../ipc/channels';

contextBridge.exposeInMainWorld('corvosScreenRegion', {
  submit: (rect: { x: number; y: number; width: number; height: number }) => {
    ipcRenderer.send(IPC_CHANNELS.SCREEN_REGION_SUBMIT, rect);
  },
  cancel: () => {
    ipcRenderer.send(IPC_CHANNELS.SCREEN_REGION_CANCEL);
  },
});
