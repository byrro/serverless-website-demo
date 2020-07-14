const baseURL = 'https://v8cc3f6f0j.execute-api.us-east-1.amazonaws.com/api/'
const template = _.template('<div class="blog-post"><h2 class="blog-post-title"><%= title %></h2><p class="blog-post-meta"><%= publishDate %> by <b><a href="maito:<%= email %>"><%= author %></a></b></p><div class="article-body"><%= body %></div><p><a id="like-btn-<%= articleID %>" class="button like-btn" href="javascript:void(0)" onclick="likeArticle(\'<%= articleID %>\')">Like it (<%= likes %>)</a></p></div>')

let blogPostsContainer = document.getElementById('blog-posts-container')
let publishArticleModal = $('#publishArticleModal')
let publishForm = {
    author: document.getElementById('pub-author'),
    email: document.getElementById('pub-email'),
    title: document.getElementById('pub-title'),
    body: document.getElementById('pub-body'),
}

publishArticleModal.on('show.bs.modal', function (e) {
    Object.values(publishForm).forEach(input => input.value = '')
})

function renderArticle(article, prepend=false) {
    let html = template({
        articleID: article['id'],
        publishDate: article['publish-datetime'],
        email: DOMPurify.sanitize(article['publisher-email']),
        author: DOMPurify.sanitize(article['publisher-name']),
        title: DOMPurify.sanitize(marked(article['title'])),
        body: DOMPurify.sanitize(marked(article['body'])),
        likes: article['likes'],
    })

    if(prepend)
        blogPostsContainer.innerHTML = html + blogPostsContainer.innerHTML
    else
        blogPostsContainer.innerHTML += html
}

function loadBlogs() {
    let url = new URL(baseURL)

    url.searchParams.append('action', 'get-latest-articles')

    fetch(url)
        .then(res => res.json())
        .then(res => {
            res.data.articles.forEach(article => {
                renderArticle(article, false)
            })
        })
        .catch(err => {
            console.error(err)
            alert('Sorry, there was an error!')
        })
}

function likeArticle(articleID) {
    let url = new URL(baseURL)

    url.searchParams.append('action', 'like-article')

    let options = {
        method: 'POST',
        headers: {
            'Content-Type': 'plain/text'
        },
        body: JSON.stringify({'article_id': articleID})
    }

    let articleLikeBtn = document.getElementById(`like-btn-${articleID}`)

    fetch(url, options)
        .then(res => res.json())
        .then(res => {
            articleLikeBtn.innerHTML = `Like it (${res.data.new_likes_count})`
        })
        .catch(err => {
            console.error(err)
            alert('Sorry, there was an error!')
        })
}

function publishArticle() {
    let url = new URL(baseURL)

    url.searchParams.append('action', 'publish-article')

    try {
        article = {
            'publisher-name': publishForm.author.value,
            'publisher-email': publishForm.email.value,
            'title': publishForm.title.value,
            'body': publishForm.body.value
        }

        Object.values(article).forEach(val => {
            if(val.length == 0)
                throw 'One or more fields is/are empty'
        })

    } catch(e) {
        alert(e)
        return
    }

    let options = {
        method: 'POST',
        headers: {
            'Content-Type': 'plain/text'
        },
        body: JSON.stringify({article: article})
    }

    fetch(url, options)
        .then(res => res.json())
        .then(res => {
            renderArticle(res.data.article, true)
            publishArticleModal.modal('hide')
            $.notify(
                {
                    'message': res.message
                }, {
                    'type': 'success',
                    'delay': 5000,
                    'placement.from': 'top',
                    'placement.align': 'center',
                    'offset': 40,
                }
            )
        })
        .catch(err => {
            console.error(err)
            $.notify(
                { 'message': 'Sorry, there was an error!' },
                { 'type': 'success', 'delay': 5000 }
            )
        })
}
