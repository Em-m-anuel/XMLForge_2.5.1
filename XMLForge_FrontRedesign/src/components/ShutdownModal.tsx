import { useState } from "react";
import { Button, Modal, useToast } from "./ui";
import { serverService } from "../api/server";

export function ShutdownModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const handleShutdown = async () => {
    setBusy(true);
    try {
      const res = await serverService.shutdown();
      toast({ kind: "success", title: "Arrêt en cours", detail: res?.message || "Serveur en cours d'arrêt" });
      setDone(true);
      // Après 1.5s, tenter fermeture fenêtre
      setTimeout(() => {
        try {
          window.close();
        } catch {}
        // Si window.close échoue (pas ouvert via script), afficher message final
        toast({ kind: "info", title: "Serveur arrêté", detail: "Vous pouvez fermer cette fenêtre. Ports 5000 et 3307 libérés." });
      }, 1200);
    } catch (e: any) {
      toast({ kind: "error", title: "Erreur arrêt", detail: e.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Fermer XMLForge ?" width="w-[460px]">
      <div className="space-y-4">
        <p className="text-[13px] leading-relaxed text-muted">
          Cette action va arrêter le serveur XMLForge et fermer l'application.
        </p>
        <div className="rounded-md border border-warn/30 bg-warn-soft/40 p-3 text-[12px] text-warn">
          <p className="font-medium">Services concernés :</p>
          <ul className="mt-1 list-disc pl-4 space-y-0.5">
            <li>Flask REST :5000</li>
            <li>TCP :3307</li>
            <li>Threads XMLForge</li>
          </ul>
          <p className="mt-2 text-[11.5px]">Les données XML persistent. Redémarrage possible, ports libérés.</p>
        </div>
        {done ? (
          <div className="rounded-md border border-ok/30 bg-ok-soft p-3 text-[12px] text-ok">
            Serveur arrêté. Vous pouvez fermer cette fenêtre.
          </div>
        ) : (
          <p className="text-[11.5px] text-dim">
            Si une transaction est active, elle sera annulée (ROLLBACK implicite via restauration snapshot non commitée). Privilégiez COMMIT avant fermeture.
          </p>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" size="sm" onClick={onClose} disabled={busy}>
            Annuler
          </Button>
          <Button variant="danger" size="sm" loading={busy} disabled={done} onClick={handleShutdown} icon="power">
            {done ? "Arrêté" : "Fermer XMLForge"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
