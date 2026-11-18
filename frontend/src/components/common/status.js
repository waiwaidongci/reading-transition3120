import {runStates,reviewStates,ledgerStates} from '../../constants/enums.js';import {esc} from '../../utils/format.js';
export function status(state){return '<span class="status '+esc(state)+'">'+esc(runStates[state]||reviewStates[state]||state)+'</span>'}
export function ledgerStatus(state){return '<span class="status ledger-'+esc(state)+'">'+esc(ledgerStates[state]||state)+'</span>'}
