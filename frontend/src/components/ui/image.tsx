import { cn } from '@/lib/utils'

export type AspectRatio =
  | 'auto'
  | '1/1'
  | '4/3'
  | '3/4'
  | '16/9'
  | '9/16'
  | '2/3'
  | '3/2'
  | '5/4'
  | '21/9'
  | '9/21'

const ASPECT_RATIO_CLASSES: Record<AspectRatio, string> = {
  auto: '',
  '1/1': 'aspect-square',
  '4/3': 'aspect-[4/3]',
  '3/4': 'aspect-[3/4]',
  '16/9': 'aspect-video',
  '9/16': 'aspect-[9/16]',
  '2/3': 'aspect-[2/3]',
  '3/2': 'aspect-[3/2]',
  '5/4': 'aspect-[5/4]',
  '21/9': 'aspect-[21/9]',
  '9/21': 'aspect-[9/21]',
}

interface ImageProps extends React.ComponentProps<'img'> {
  aspectRatio?: AspectRatio
  forceNoLazy?: boolean
}

function Image({
  src,
  alt = '',
  aspectRatio = 'auto',
  forceNoLazy = false,
  className,
  ...props
}: ImageProps) {
  const aspectClass = ASPECT_RATIO_CLASSES[aspectRatio] ?? ''

  return (
    <div className={cn(aspectClass, 'w-full', className)}>
      <img
        alt={alt}
        className="h-full w-full object-cover"
        loading={forceNoLazy ? 'eager' : 'lazy'}
        src={src}
        {...props}
      />
    </div>
  )
}

export { Image }
