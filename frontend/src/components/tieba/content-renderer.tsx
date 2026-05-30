import { getMediaUrl } from '@/lib/api'

interface ContentFrag {
  type: number
  text?: string
  src?: string
  filename?: string
  desc?: string
  link?: string
  width?: number
  height?: number
  duration?: number
  c?: string
}

export function ContentRenderer({
  contents,
  forumName,
  mediaFiles,
}: {
  contents: string
  forumName: string
  mediaFiles: string[]
}) {
  let frags: ContentFrag[]
  try {
    const parsed = JSON.parse(contents)
    if (!Array.isArray(parsed)) return <span>{contents}</span>
    frags = parsed
  } catch {
    return <span>{contents}</span>
  }

  if (frags.length === 0) return null

  return (
    <>
      {frags.map((frag, i) => (
        <FragRenderer key={i} frag={frag} forumName={forumName} mediaFiles={mediaFiles} />
      ))}
    </>
  )
}

function FragRenderer({
  frag,
  forumName,
  mediaFiles,
}: {
  frag: ContentFrag
  forumName: string
  mediaFiles: string[]
}) {
  switch (frag.type) {
    // text / line break
    case 0:
    case 1:
      if (frag.text === '\n') return <br />
      return <span>{frag.text}</span>

    // image
    case 2: {
      if (frag.filename) {
        const mediaPath = mediaFiles.find((f) => f.includes(frag.filename!))
        if (mediaPath) {
          return (
            <img
              src={getMediaUrl(forumName, mediaPath)}
              alt=""
              className="my-[6px] block max-w-full"
              style={{
                maxHeight: '500px',
                width: frag.width ? `${Math.min(frag.width, 580)}px` : undefined,
              }}
              loading="lazy"
            />
          )
        }
      }
      if (frag.src) {
        return (
          <img
            src={frag.src}
            alt=""
            className="my-[6px] block max-w-full"
            style={{ maxHeight: '500px' }}
            loading="lazy"
          />
        )
      }
      return null
    }

    // @mention
    case 3:
      return (
        <a
          href={`https://tieba.baidu.com/home/main?un=${encodeURIComponent(frag.text || '')}`}
          target="_blank"
          rel="noreferrer"
          className="text-[#4096ff] hover:underline"
        >
          @{frag.text}
        </a>
      )

    // link
    case 4:
      return (
        <a
          href={frag.link || frag.src}
          className="text-[#4096ff] hover:underline"
          target="_blank"
          rel="noreferrer"
        >
          {frag.text || frag.src || '链接'}
        </a>
      )

    // video
    case 5:
      if (frag.src) {
        return (
          <video
            src={frag.src}
            controls
            className="my-[6px] block max-w-full rounded-[4px]"
            style={{ maxHeight: '400px', objectFit: 'contain' }}
          />
        )
      }
      return frag.text ? <span className="text-[#888]">[视频: {frag.text}]</span> : null

    // voice/audio
    case 6:
      if (frag.src) {
        return (
          <div className="my-[4px] inline-flex h-[30px] items-center gap-[4px] rounded-[16px] bg-[#4096ff] px-[12px] text-[12px] text-white">
            <span>🎵</span>
            <span>{frag.duration ? `${frag.duration}"` : '语音'}</span>
          </div>
        )
      }
      return <span className="text-[#888]">[语音]</span>

    // emoji / emoticon
    case 10: {
      if (frag.src) {
        return (
          <img
            src={frag.src}
            alt={frag.desc || frag.text || ''}
            title={frag.desc || frag.text || ''}
            className="inline-block h-auto w-auto align-middle"
            style={{ maxHeight: '30px', maxWidth: '30px' }}
          />
        )
      }
      if (frag.c) {
        const emojiUrl = `https://tb2.bdstatic.com/tb/editor/images/client/${frag.c}.png`
        return (
          <img
            src={emojiUrl}
            alt={frag.desc || frag.text || ''}
            title={frag.desc || frag.text || ''}
            className="inline-block h-auto w-auto align-middle"
            style={{ maxHeight: '30px', maxWidth: '30px' }}
          />
        )
      }
      if (frag.text && frag.text.startsWith('image_emoticon')) {
        const emojiUrl = `https://tb2.bdstatic.com/tb/editor/images/client/${frag.text}.png`
        return (
          <img
            src={emojiUrl}
            alt={frag.desc || ''}
            title={frag.desc || ''}
            className="inline-block h-auto w-auto align-middle"
            style={{ maxHeight: '30px', maxWidth: '30px' }}
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
          />
        )
      }
      return <span title={frag.desc || ''}>{frag.desc || frag.text || '😊'}</span>
    }

    // scrape error
    case -1:
      return (
        <div className="my-[4px] inline-block rounded border border-[#ffccc7] bg-[#fff2f0] px-[8px] py-[4px] text-[12px] text-[#cf1322]">
          {frag.text || '[抓取错误]'}
        </div>
      )

    default:
      return frag.text ? <span>{frag.text}</span> : null
  }
}
