/**
 * Store index — ré-exporte le store principal pour nouvelle structure
 * Permet import depuis @/store ou @/store/index
 * Le store principal reste dans src/store.tsx pour compatibilité,
 * mais cette entrée prépare la future modularisation (auth, databases, tables, etc)
 */

export * from "../store";
export { StoreProvider, useStore } from "../store";
