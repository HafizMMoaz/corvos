import { type App, Modal, Notice, Setting } from "obsidian";
import type CorvosPlugin from "./main";
import { STATUS_VISUALS } from "./status-visuals";

/** Live status panel reachable from the status bar / command palette. */
export class StatusModal extends Modal {
	private readonly plugin: CorvosPlugin;
	private readonly onChange = (): void => this.render();

	constructor(app: App, plugin: CorvosPlugin) {
		super(app);
		this.plugin = plugin;
	}

	onOpen(): void {
		this.setTitle("Corvos status");
		this.plugin.onStatusChange(this.onChange);
		this.render();
	}

	onClose(): void {
		this.plugin.offStatusChange(this.onChange);
		this.contentEl.empty();
	}

	private render(): void {
		const { contentEl, plugin } = this;
		contentEl.empty();
		const s = plugin.settings;

		const rows: Array<[string, string]> = [
			["Status", STATUS_VISUALS[plugin.lastStatus.kind].label],
			[
				"Last sync",
				s.lastSyncAt ? new Date(s.lastSyncAt).toLocaleString() : "-",
			],
			[
				"Last reconcile",
				s.lastReconcileAt
					? new Date(s.lastReconcileAt).toLocaleString()
					: "-",
			],
			["Files synced", String(s.filesSynced ?? 0)],
			["Queue depth", String(plugin.queueDepth)],
			[
				"Capabilities",
				plugin.serverCapabilities.length
					? plugin.serverCapabilities.join(", ")
					: "(not yet handshaken)",
			],
		];
		for (const [label, value] of rows) {
			new Setting(contentEl).setName(label).setDesc(value);
		}

		new Setting(contentEl)
			.addButton((btn) =>
				btn
					.setButtonText("Re-sync entire vault")
					.setCta()
					.onClick(async () => {
						btn.setDisabled(true);
						try {
							await plugin.engine.maybeReconcile(true);
							new Notice("Corvos: re-sync requested.");
						} catch (err) {
							new Notice(
								`Corvos: re-sync failed - ${(err as Error).message}`,
							);
						} finally {
							btn.setDisabled(false);
						}
					}),
			)
			.addButton((btn) => btn.setButtonText("Close").onClick(() => this.close()));
	}
}
