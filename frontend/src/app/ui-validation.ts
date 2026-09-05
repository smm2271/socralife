import validate from './ui-validator.generated.js';
import type { UIComponent } from './contracts';
export function validUi(value:unknown): value is UIComponent { return !!validate(value); }
export function validatedUi(values:unknown): UIComponent[] { if(!Array.isArray(values)) return []; return values.filter(validUi); }
