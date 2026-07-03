import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'id.sakoo.finance',
  appName: 'SakooFinance',
  webDir: 'out',
  server: {
    url: "http://192.168.1.102:3000",
    cleartext: true
  }
};

export default config;
