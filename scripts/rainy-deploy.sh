#! /bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

ENV=""
INFRA=""
REGISTRY=""
YUM=""
DEFAULT_EMAIL_RECEIVERS="chenjie1@sensetime.com;lizhihui@sensetime.com;wanyongzhen@sensetime.com;zhangmin@sensetime.com;huomingming@sensetime.com;piaoyuankui@sensetime.com;liuyuan@sensetime.com"
PRODUCT="SU"
# ENV="env-stage-a"
# INFRA="infra-ansible-1.1.0-201804101231.rpm"
# INFRA="master"
# INFRA="branch-abc-def"

# REGISTRY="infra-distribution-registry-v1.1.0-201804091556.tar.gz"
# REGISTRY="online"

# YUM="infra-distribution-yum.tar.gz"
# YUM="infra-distribution-yum-minimal.tar.gz"
# YUM="online"

git_username="${GIT_USERNAME}"
git_password="${GIT_PASSWORD}"

function download_files {
    yum install wget git -y

    if [ $REGISTRY != "online" ]; then
        echo "start downloading $REGISTRY"
        wget --progress=bar:force -O $DIR/$REGISTRY  http://sz.rainy.sensesecurity.net/distribution/$REGISTRY
        tar zxvf $DIR/$REGISTRY -C $DIR
        rm -rf $DIR/$REGISTRY 
        bash $DIR/infra-distribution-registry/install.sh
    else
        echo "use online registry service."
    fi

    if [ $YUM != "online" ]; then
        echo "start downloading $YUM"
        wget --progress=bar:force -O $DIR/$YUM  http://sz.rainy.sensesecurity.net/distribution/$YUM
        tar zxvf $DIR/$YUM -C $DIR
        rm -rf $DIR/$YUM
        bash $DIR/infra-distribution-yum*/install.sh

    else
        echo "use online yum service."
    fi

    if [ $INFRA != "master"  ] && [[ $INFRA != *"branch-"* ]]; then
        echo "start downloading $INFRA"
        wget --progress=bar:force -O $DIR/$INFRA http://sz.rainy.sensesecurity.net/yum/infra/$INFRA

        yum localinstall $DIR/$INFRA -y
        rm -rf $DIR/$INFRA
        
    else
        yum install -y python-pip

        git clone http://$git_username:$git_password@gitlab.sz.sensetime.com/rainy/infra/infra-ansible.git $DIR/infra-ansible
        cd $DIR/infra-ansible
        if [[ $INFRA = *"branch-"*  ]]; then
            branch=${INFRA/branch-/}
            git fetch -av --tags
            git checkout $branch
        fi
        git submodule update --init
        pip install -r requirements.txt
        pip install -U pip
        pip install -U setuptools
        python setup.py install
    fi

    

    if [[ $INFRA = "branch-v2.2" ||  $INFRA = *"ansible-v2.2.0"*  ]]; then
    
        # if [ $PRODUCT = "su" ]; then
            
        #     cd /data
        #     pwd
        #     wget --progress=bar:force -O /data/models-su.tar.gz http://sz.rainy.sensesecurity.net/distribution/v2.2/models-su.tar.gz
        #     tar zxvf /data/models-su.tar.gz -C /data
        #     mv /data/RAINY-v2.2-models-local/model_cache  /data/client-model-cache
        #     rm -rf /data/models-su.tar.gz
        # fi

        # if [ $PRODUCT = "foundry" ]; then
        cd /data
        pwd
        wget --progress=bar:force -O /data/models-foundry.tar.gz http://sz.rainy.sensesecurity.net/distribution/v2.2/models-foundry.tar.gz
        tar zxvf /data/models-foundry.tar.gz -C /data
        mv /data/RAINY-v2.2-models /data/model-cache
        rm -rf /data/models-foundry.tar.gz
        # fi
    fi
}

function init_infra {
    yum install wget git sshpass net-tools -y

    mkdir -p $DIR/rainy && cd $DIR/rainy && infra init .

    git clone --depth 1 http://$git_username:$git_password@gitlab.sz.sensetime.com/rainy/infra/env.git /tmp/infra-envs

    /usr/bin/cp     /tmp/infra-envs/$ENV/inventory .
    /usr/bin/cp -r  /tmp/infra-envs/$ENV/group_vars .
    /usr/bin/cp -rL /tmp/infra-envs/$ENV/license-ca .
}

function is_k8s_pending_pod {
   pending=$(kubectl get pods --all-namespaces | grep -v NAMESPACE | grep -v Running)
   if [ -z "$pending" ]; then
      false;
   else
      true;
   fi
   return $?;
}

function deploy_infra {
    cd $DIR/rainy

    # make sure to enable rc.local script
    systemctl enable rc-local

    # make rc.local executable
    chmod +x /etc/rc.d/rc.local

    # clear existing next reboot script
    sed -i /rainy-deploy/d /etc/rc.d/rc.local


    ### step 1

    ########### set next reboot script before running `init-local-first.yml`
    echo "nohup /bin/bash $DIR/rainy-deploy.sh --env $ENV --infra $INFRA --registry $REGISTRY --yum $YUM --receivers \"$RECEIVERS\" deploy >> /tmp/rainy-deploy.log 2>&1 & " >> /etc/rc.d/rc.local

    echo "TIMEIT: $(date): start ansible-playbook init-local-first.yml in $DIR/rainy.."
    (echo y; echo y; ) | ansible-playbook init-local-first.yml
    ret=$?

    ########### remove next reboot script.
    sed -i /rainy-deploy/d /etc/rc.d/rc.local

    if [ $ret -ne 0 ]; then
        echo "!!!ERROR: ansible-playbook init-local-first.yml failed! check /tmp/rainy-deploy.log. now stop.."
        exit_with 1 "!!!ERROR: ansible-playbook init-local-first.yml failed! check /tmp/rainy-deploy.log. now stop.."
    fi
    echo "TIMEIT: $(date): ansible-playbook init-local-first.yml success!"

    ### step 2

    ########### set next reboot script before running `prepare.yml`
    echo "nohup /bin/bash $DIR/rainy-deploy.sh --env $ENV --infra $INFRA --registry $REGISTRY --yum $YUM deploy >> /tmp/rainy-deploy.log 2>&1 & " >> /etc/rc.d/rc.local

    echo "TIMEIT: $(date): start ansible-playbook prepare.yml in $DIR/rainy.."
    (echo y; echo y;) | ansible-playbook prepare.yml
    ret=$?

    ########## remove next reboot script.
    sed -i /rainy-deploy/d /etc/rc.d/rc.local

    if [ $ret -ne 0 ]; then
        echo "!!!ERROR: ansible-playbook prepare.yml failed! check /tmp/rainy-deploy.log. now stop.."
        exit_with 1 "!!!ERROR: ansible-playbook prepare.yml failed! check /tmp/rainy-deploy.log. now stop.."
    fi
    echo "TIMEIT: $(date): ansible-playbook prepare.yml success!"

    # remove next reboot script, whenever it is successfully prepared or failed.
    sed -i /rainy-deploy/d /etc/rc.d/rc.local

    if [ $ret -ne 0 ]; then
        exit_with 1 "!!!ERROR: failed to remove next boot script in /etc/rc.d/rc.local, for safety, stop now.."
    fi

    ### step 3

    echo "TIMEIT: $(date): start ansible-playbook deploy.yml in $DIR/rainy.."
    ansible-playbook deploy.yml --flush-cache
    ret=$?
    if [ $ret -ne 0 ]; then
        echo "!!!ERROR: ansible-playbook deploy.yml failed! check /tmp/rainy-deploy.log. now stop.."
        exit_with 1 "!!!ERROR: ansible-playbook deploy.yml failed! check /tmp/rainy-deploy.log. now stop.."
    fi
    echo "TIMEIT: $(date): ansible-playbook deploy.yml success!"


    echo "before play apps.yml, check all pod running."
    while is_k8s_pending_pod; do
        sleep 1
        echo "before play apps.yml, still not all Running"
    done
    echo "before play apps.yml, pod all running, good."


    ### step 4

    echo "TIMEIT: $(date): start ansible-playbook apps.yml in $DIR/rainy.."
    ansible-playbook apps.yml
    ret=$?
    if [ $ret -ne 0 ]; then
        echo "!!!ERROR: ansible-playbook apps.yml failed! check /tmp/rainy-deploy.log. now stop.."
        exit_with 1 "!!!ERROR: ansible-playbook apps.yml failed! check /tmp/rainy-deploy.log. now stop.."
    fi
    echo "TIMEIT: $(date): ansible-playbook apps.yml finished!"


    echo "after play apps.yml, check all pod running."
    #while is_k8s_pending_pod; do
    #wait 15m if soft license will all running,else no care
    sleep 900
    echo "after play apps.yml, still not all Running"
    #done
    echo "after play apps.yml, all processes have been executed."

    echo "INFO: $(date): ansible-playbook apps.yml success!"

    ### step 5 sensenodal need
    if [ -f gateway.yml ]; then
        echo "TIMEIT: $(date): start ansible-playbook gateway.yml in $DIR/rainy.."
        ansible-playbook gateway.yml
        echo "TIMEIT: $(date): ansible-playbook gateway.yml finished!"

        exit_with 0 "INFO: $(date): ansible-playbook gateway.yml success!"
    fi

    exit_with 0 "INFO: $(date): ansible-playbook apps.yml success!"

}



function send_mail {
    title=$1
    messages="$2"

    ip=$(ifconfig | sed -En 's/127.0.0.1//;s/.*inet (addr:)?(([0-9]*\.){3}[0-9]*).*/\2/p' | grep -v '172.17.0.1' | grep -v '10.233')
    systems="ip: $ip"

    body="${title}, messages:
${messages}

system infos:
${systems}"

    mail="http://system.bj.sensetime.com/sendmail.php"

    set -x
    curl -F "message=${body}" -F "mailto=${RECEIVERS}" -F "title=${title}" ${mail} > /dev/null 2>&1
}


# exit_with 1 "!!!ERROR: ansible-playbook deploy.yml failed! check /tmp/rainy-deploy.log. now stop.."
function exit_with {
    if [ "$1" == "1"  ]; then
        title_str="${ENV} deploy failed"
    else
        title_str="${ENV} deploy success"
    fi
    body_str=$2

    send_mail "$title_str" "$body_str"

    exit "$1"
}


function print_usage {
    echo "parsed input: bash /root/rainy-deploy.sh --env $ENV --registry $REGISTRY --yum $YUM --infra $INFRA $ACTION"
    echo ""

    echo "usage: bash /root/rainy-deploy.sh --env [ENV] --registry [REGISTRY] --yum [YUM] --infra [INFRA] [COMMAND]"
    echo ""
    echo "  ENV:    which env to deploy. It must be a sub dir in 10.9.242.6:/root/pxe/env, example: env-stage-a"
    echo "  REGISTRY:   infra-distribution-registry version. full name, example: infra-distribution-regitry-v1.1.0-201804091556.tar.gz"
    echo "  YUM:        infra-distribution version. full name, example: infra-distribution-yum.tar.gz"
    echo "  INFRA:      infra-ansible version. full name, example: infra-ansible-1.1.0-201804101231.rpm"
    echo ""
    echo "  COMMAND:"
    echo "      download            download distribution tarbar and infra-ansible rpm to the script directory, along side rainy-deploy.sh. localinstall rpm & distribution"
    echo "      init                init rainy folder for future deploy, and copy env all.yml from 10.9.242.6"
    echo "      deploy              run ansible playbooks"
    echo "      default             combine 'download' & 'init' & 'deploy' "
    echo ""

}

function main {
    while [[ $# -gt 0 ]]
    do
        key="$1"
        case $key in
            --env)
                ENV="$2"
                shift
                shift
                ;;

            --registry)
                REGISTRY="$2"
                shift
                shift
                ;;
            --yum)
                YUM="$2"
                shift
                shift
                ;;
            --infra)
                INFRA="$2"
                shift
                shift
                ;;
            --receivers)
                RECEIVERS="$2"
                shift
                shift
                ;;

            --product)
                PRODUCT="$2"
                shift
                shift
                ;;

            download)
                ACTION="download"
                shift
                ;;

            init)
                ACTION="init"
                shift
                ;;

            deploy)
                ACTION="deploy"
                shift
                ;;

            default)
                ACTION="default"
                shift
                ;;

            *)
                print_usage;
                exit 1;

        esac
    done

    if [ "${ENV}z" == "z" ] || [  "${INFRA}z" == "z" ] || [ "${REGISTRY}z" == "z" ] || [ "${YUM}z" == "z" ] || [ "${ACTION}z" == "z" ]; then
        print_usage;
        exit 1;
    fi
    if [ "${RECEIVERS}z" == "z" ]; then
        RECEIVERS=$DEFAULT_EMAIL_RECEIVERS
    fi

    if [ $ACTION == "download" ]; then
        download_files
    elif [ $ACTION == "init" ]; then
        init_infra
    elif [ $ACTION == "deploy" ]; then
        deploy_infra
    elif [ $ACTION == "default" ]; then
        download_files
        init_infra
        deploy_infra
    else
        print_usage;
        exit 1
    fi

}

main "$@"
