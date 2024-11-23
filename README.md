### Create `.env` file and add the following keys
```shell
OPENAI_API_KEY=*********
ASSISTANT_ID=*********
```


### build docker
```
docker build -t poc .
```

### run docker
```
 docker run -p 8001:8001 -e HOST=0.0.0.0 poc
```
