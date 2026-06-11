declare module 'diff' {
  export interface DiffPart {
    value: string
    added?: boolean
    removed?: boolean
    count?: number
  }

  export function diffWords(oldStr: string, newStr: string): DiffPart[]
  export function diffChars(oldStr: string, newStr: string): DiffPart[]
  export function diffLines(oldStr: string, newStr: string): DiffPart[]
  export function diffTrimmedLines(oldStr: string, newStr: string): DiffPart[]
  export function diffSentences(oldStr: string, newStr: string): DiffPart[]
  export function diffWordsWithSpace(oldStr: string, newStr: string): DiffPart[]
  export function diffCss(oldStr: string, newStr: string): DiffPart[]
  export function diffJson(oldObj: object, newObj: object): DiffPart[]
  export function diffArrays(oldArr: any[], newArr: any[]): DiffPart[]
}
