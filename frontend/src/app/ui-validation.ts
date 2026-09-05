import Ajv from 'ajv';
import schema from '../../../contracts/ui.schema.json';
import type { UIComponent } from './contracts';
const validate = new Ajv({allErrors:true,strict:false}).compile(schema);
export function validUi(value:unknown): value is UIComponent { return !!validate(value); }
export function validatedUi(values:unknown): UIComponent[] { if(!Array.isArray(values)) return []; return values.filter(validUi); }

